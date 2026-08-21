"""Exact donor parity and production contracts for Hot-Stop Rebound."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import random
from typing import cast

import pytest

import lottolab.strategies.adapters.biglotto_hot_stop_rebound as hot_stop_module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave6 import (
    HOT_STOP_REBOUND_METHOD_ID,
    LegacySourceNativeWave6Request,
    generate_legacy_source_native_wave6_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_hot_stop_rebound import (
    BigLottoHotStopReboundAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae"
SOURCE_SHA256 = "1794a8c507aed174efe13310a3a3b7774158149931ce70101a2cfb729d54b2f5"
SOURCE_BLOB = "b3758b5c855fe42bae5d9a9de5b66b8079755ba7"
PARAMETER_GRID = (
    (12, 8),
    (12, 10),
    (15, 8),
    (15, 10),
    (15, 12),
    (18, 8),
    (18, 10),
    (20, 10),
)


def _random_history(
    count: int,
    *,
    seed: int | None = None,
) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(count if seed is None else seed)
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(count)
    )


def _retained_history(
    history: tuple[CausalDrawRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=row.draw,
            numbers=cast(Ticket, row.numbers),
        )
        for row in history
    )


def _retained_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[Ticket, ...]:
    return generate_legacy_source_native_wave6_portfolio(
        LegacySourceNativeWave6Request(
            legacy_method_id=HOT_STOP_REBOUND_METHOD_ID,
            target_draw_number=str(len(history) + 1),
            history=_retained_history(history),
        )
    ).tickets


def test_authoritative_identity_is_unique_cataloged_fixed_portfolio() -> None:
    retained = next(
        record
        for record in load_full_strategy_catalog().records
        if record.strategy_id == STRATEGY_ID
    )
    assert retained.legacy_method_id == HOT_STOP_REBOUND_METHOD_ID
    assert retained.source_commit == "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
    assert retained.source_blob_id == SOURCE_BLOB
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.native_ticket_semantics == (
        "FROZEN_SOURCE_NATIVE_EIGHT_SOURCE_PARAMETER_GRID_CONFIGURATIONS_IN_DECLARATION_ORDER"
    )
    assert retained.ticket_duplicate_semantics == (
        "PRESERVE_NATIVE_POSITIONAL_DUPLICATES_ACROSS_SOURCE_CONFIGURATIONS"
    )

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    strategy_ids = tuple(item.strategy_id for item in catalog)
    assert len(strategy_ids) == 82
    assert strategy_ids[-4:] == (
        "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6",
        STRATEGY_ID,
        "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94",
        "legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e",
    )
    assert strategy_ids[:-3].count(STRATEGY_ID) == 0
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (8, 8)
    assert descriptor.min_history == 200
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "donor_parity:EXACT_OUTPUT_PARITY" in descriptor.provenance
    assert "randomness:NONE_DETERMINISTIC" in descriptor.provenance
    assert "runtime_boundary:CALLER_SUPPLIED_CAUSAL_HISTORY_NO_DB" in (descriptor.provenance)

    registry = ExecutableRegistry(catalog)
    assert registry.load_adapter(STRATEGY_ID) is BigLottoHotStopReboundAdapter


@pytest.mark.parametrize("history_count", (200, 275, 450))
def test_complete_target_output_matches_retained_reference(
    history_count: int,
) -> None:
    history = _random_history(history_count)

    actual = BigLottoHotStopReboundAdapter().get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert actual == _retained_tickets(history)
    assert len(actual) == 8
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and ticket == tuple(sorted(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


def test_statistics_preserve_frequency_and_true_gap_windows() -> None:
    history = tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
            numbers=(1, 2, 3, 4, 5, 6) if index < 190 else (7, 8, 9, 10, 11, 12),
        )
        for index in range(200)
    )

    frequencies, gaps = hot_stop_module._hot_stop_statistics(history)

    assert tuple(frequencies[number] for number in range(1, 7)) == (90,) * 6
    assert tuple(frequencies[number] for number in range(7, 13)) == (10,) * 6
    assert tuple(gaps[number] for number in range(1, 7)) == (10,) * 6
    assert tuple(gaps[number] for number in range(7, 13)) == (0,) * 6
    assert frequencies[49] == 0
    assert gaps[49] == 200


def test_ticket_ranking_preserves_source_ties_and_frequency_fill() -> None:
    frequencies = {number: 0 for number in range(1, 50)}
    gaps = {number: 0 for number in range(1, 50)}
    frequencies.update({1: 30, 2: 30, 10: 20, 11: 20, 12: 25, 13: 12})
    gaps.update({10: 10, 11: 10, 12: 8, 13: 8})

    assert hot_stop_module._hot_stop_ticket(
        frequencies=frequencies,
        gaps=gaps,
        frequency_threshold=12,
        gap_threshold=8,
    ) == (1, 2, 10, 11, 12, 13)


def test_parameter_grid_order_and_positional_duplicates_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int]] = []

    def _same_ticket(
        *,
        frequencies: dict[int, int],
        gaps: dict[int, int],
        frequency_threshold: int,
        gap_threshold: int,
    ) -> tuple[int, ...]:
        del frequencies, gaps
        calls.append((frequency_threshold, gap_threshold))
        return (1, 2, 3, 4, 5, 6)

    monkeypatch.setattr(hot_stop_module, "_hot_stop_ticket", _same_ticket)

    tickets = hot_stop_module._hot_stop_rebound_tickets(_random_history(200))

    assert tuple(calls) == PARAMETER_GRID
    assert tickets == ((1, 2, 3, 4, 5, 6),) * 8


def test_invalid_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoHotStopReboundAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_random_history(199), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_random_history(200)), LotteryType.BIG_LOTTO)
    duplicate_identity = list(_random_history(200))
    duplicate_identity[-1] = CausalDrawRow(
        draw=duplicate_identity[0].draw,
        date=duplicate_identity[-1].date,
        numbers=duplicate_identity[-1].numbers,
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(tuple(duplicate_identity), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_random_history(200), LotteryType.DAILY_539)


def test_production_generation_dispatches_complete_deterministic_portfolio() -> None:
    history = _random_history(275)
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )

    first = build_production_generate_portfolio().execute(request)
    second = build_production_generate_portfolio().execute(request)
    wrong_path = build_production_generate_one_bet().execute(request)

    assert first.status is GeneratePortfolioStatus.OK
    assert first.numbers == _retained_tickets(history)
    assert second == first
    assert wrong_path.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert wrong_path.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
