"""Exact donor parity and production contracts for Radical Gap migration."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import random
from typing import cast

import pytest

import lottolab.strategies.adapters.biglotto_radical_gap as radical_module
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave31 import (
    RADICAL_BACKTEST_METHOD_ID,
    LegacySourceNativeWave31Request,
    LegacySourceNativeWave31SourceError,
    generate_legacy_source_native_wave31_portfolio,
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
from lottolab.strategies.adapters.biglotto_radical_gap import (
    BigLottoRadicalGapBacktestAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6"
SOURCE_SHA256 = "e54cc0812bc6fff14a259282a37821810d264c023c4fb87517305b511db08fd9"


def _history(count: int) -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(count):
        values = sorted(((index * 7 + offset * 5) % 49) + 1 for offset in range(6))
        rows.append(
            CausalDrawRow(
                draw=str(index + 1),
                date=f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}",
                numbers=tuple(values),
            )
        )
    return tuple(rows)


def _random_history(count: int, *, seed: int = 1) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(seed)
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
    return generate_legacy_source_native_wave31_portfolio(
        LegacySourceNativeWave31Request(
            legacy_method_id=RADICAL_BACKTEST_METHOD_ID,
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
    assert retained.legacy_method_id == "tools/backtest_radical_strategy.py"
    assert retained.source_blob_id == "c460fb65561000a1e3a0d5558133784603860f2c"
    assert retained.source_sha256 == SOURCE_SHA256
    assert retained.native_ticket_semantics == (
        "FROZEN_SOURCE_NATIVE_TWO_POSITIONAL_GAP_TICKETS_EXCLUDING_01_19_THEN_20_29"
    )
    assert retained.ticket_duplicate_semantics == (
        "PRESERVE_FROZEN_POSITIONAL_GAP_TICKET_DUPLICATES"
    )

    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert sum(item.strategy_id == STRATEGY_ID for item in catalog) == 1
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count_bounds == (2, 2)
    assert descriptor.min_history == 50
    assert f"legacy_source_sha256:{SOURCE_SHA256}" in descriptor.provenance
    assert "donor_parity:EXACT_OUTPUT_PARITY" in descriptor.provenance
    assert "randomness:NONE_DETERMINISTIC" in descriptor.provenance

    registry = ExecutableRegistry(catalog)
    assert registry.load_adapter(STRATEGY_ID) is BigLottoRadicalGapBacktestAdapter


@pytest.mark.parametrize("history_count", (50, 200, 300, 350))
def test_complete_target_output_matches_retained_reference(
    history_count: int,
) -> None:
    history = _random_history(history_count)

    actual = BigLottoRadicalGapBacktestAdapter().get_bets(
        history,
        LotteryType.BIG_LOTTO,
    )

    assert actual == _retained_tickets(history)
    assert len(actual) == 2
    assert all(
        len(ticket) == 6
        and len(set(ticket)) == 6
        and ticket == tuple(sorted(ticket))
        and all(1 <= number <= 49 for number in ticket)
        for ticket in actual
    )


def test_known_wave31_fixture_preserves_gap_ticket_order() -> None:
    assert BigLottoRadicalGapBacktestAdapter().get_bets(
        _history(200),
        LotteryType.BIG_LOTTO,
    ) == (
        (24, 29, 34, 39, 44, 49),
        (10, 11, 12, 14, 16, 17),
    )


def test_invalid_source_output_closure_matches_retained_reference() -> None:
    history = _history(300)
    with pytest.raises(LegacySourceNativeWave31SourceError):
        _retained_tickets(history)
    with pytest.raises(InvalidOutput, match="fewer than six legal candidates"):
        BigLottoRadicalGapBacktestAdapter().get_bets(
            history,
            LotteryType.BIG_LOTTO,
        )


def test_deterministic_latest_300_window_is_causal_and_isolated() -> None:
    history = _random_history(350)
    adapter = BigLottoRadicalGapBacktestAdapter()
    expected = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    changed_outside_window = tuple(
        CausalDrawRow(
            draw=row.draw,
            date=row.date,
            numbers=(1, 2, 3, 4, 5, 6),
        )
        if index < 50
        else row
        for index, row in enumerate(history)
    )

    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == expected
    assert adapter.get_bets(history[-300:], LotteryType.BIG_LOTTO) == expected
    assert (
        adapter.get_bets(
            changed_outside_window,
            LotteryType.BIG_LOTTO,
        )
        == expected
    )


def test_positional_duplicate_tickets_are_not_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _same_component_ticket(
        method_name: str,
        history: tuple[CausalDrawRow, ...],
    ) -> tuple[int, ...]:
        del method_name, history
        return (30, 31, 32, 33, 34, 35)

    monkeypatch.setattr(
        radical_module,
        "_engine_ticket",
        _same_component_ticket,
    )

    assert BigLottoRadicalGapBacktestAdapter().get_bets(
        _history(50),
        LotteryType.BIG_LOTTO,
    ) == (
        (30, 31, 32, 33, 34, 35),
        (30, 31, 32, 33, 34, 35),
    )


def test_component_failure_closes_without_an_alternate_predictor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failed_component(
        method_name: str,
        history: tuple[CausalDrawRow, ...],
    ) -> tuple[int, ...]:
        del method_name, history
        raise RuntimeError("component failed")

    monkeypatch.setattr(radical_module, "_engine_ticket", _failed_component)

    with pytest.raises(InvalidOutput, match="fewer than six legal candidates"):
        BigLottoRadicalGapBacktestAdapter().get_bets(
            _history(50),
            LotteryType.BIG_LOTTO,
        )


def test_invalid_insufficient_and_unsupported_inputs_fail_closed() -> None:
    adapter = BigLottoRadicalGapBacktestAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(_history(49), LotteryType.BIG_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(list(_history(50)), LotteryType.BIG_LOTTO)
    duplicate_identity = list(_history(50))
    duplicate_identity[-1] = CausalDrawRow(
        draw=duplicate_identity[0].draw,
        date=duplicate_identity[-1].date,
        numbers=duplicate_identity[-1].numbers,
    )
    with pytest.raises(InvalidOutput, match="identities must be unique"):
        adapter.get_bets(tuple(duplicate_identity), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(50), LotteryType.DAILY_539)


def test_production_generation_dispatches_the_complete_portfolio() -> None:
    history = _history(200)
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
