"""Executable old/new parity and production contracts for the 2-bet hedge."""

from __future__ import annotations

import sqlite3

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters import BigLotto2BetHedgingAdapter
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__biglotto_2bet_hedging__07a3aa455074"


def _history(length: int, mode: str = "cycle") -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(length):
        if mode == "cycle":
            numbers = tuple(
                sorted({((index * 7 + offset * 5) % 49) + 1 for offset in range(6)})
            )
        elif mode == "edge":
            numbers = (1, 2, 3, 4, 5, 49) if index % 2 == 0 else (44, 45, 46, 47, 48, 49)
        else:
            numbers = (1, 2, 3, 4, 5, 6) if index % 2 == 0 else (44, 45, 46, 47, 48, 49)
        rows.append(
            CausalDrawRow(
                draw=f"hedging-{mode}-{index}",
                date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                numbers=numbers,
            )
        )
    return tuple(rows)


DONOR_GOLDENS: dict[tuple[str, int], tuple[tuple[int, ...], ...]] = {
    ("cycle", 1): ((1, 6, 11, 16, 21, 26), (2, 3, 12, 13, 22, 23)),
    ("cycle", 2): ((8, 13, 18, 23, 28, 33), (1, 6, 11, 16, 21, 26)),
    ("cycle", 29): ((1, 6, 11, 16, 21, 26), (8, 13, 18, 23, 28, 33)),
    ("cycle", 30): ((8, 13, 18, 23, 28, 33), (15, 20, 25, 30, 35, 40)),
    ("cycle", 31): ((15, 20, 25, 30, 35, 40), (22, 27, 32, 37, 42, 47)),
    ("cycle", 50): ((1, 6, 11, 16, 21, 26), (8, 13, 18, 23, 28, 33)),
    ("cycle", 500): ((15, 20, 25, 30, 35, 40), (22, 27, 32, 37, 42, 47)),
    ("edge", 2): ((44, 45, 46, 47, 48, 49), (6, 7, 11, 12, 21, 22)),
    ("edge", 30): ((44, 45, 46, 47, 48, 49), (1, 2, 3, 4, 5, 49)),
    ("edge", 51): ((1, 2, 3, 4, 5, 49), (44, 45, 46, 47, 48, 49)),
    ("tie", 30): ((44, 45, 46, 47, 48, 49), (1, 2, 3, 4, 5, 6)),
}


@pytest.mark.parametrize(("mode", "length"), tuple(DONOR_GOLDENS))
def test_matches_executed_revived_donor_golden(mode: str, length: int) -> None:
    assert BigLotto2BetHedgingAdapter().get_bets(
        _history(length, mode), LotteryType.BIG_LOTTO
    ) == DONOR_GOLDENS[(mode, length)]


def test_default_hedge_preserves_ticket_order_and_is_deterministic() -> None:
    adapter = BigLotto2BetHedgingAdapter()
    history = _history(500)
    first = adapter.get_bets_with_emission(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets_with_emission(history, LotteryType.BIG_LOTTO)

    assert first == second
    assert tuple(execution.emitted_main_numbers for execution in first) == DONOR_GOLDENS[
        ("cycle", 500)
    ]
    assert tuple(execution.legal_main_numbers for execution in first) == DONOR_GOLDENS[
        ("cycle", 500)
    ]
    assert all(execution.special_number is None for execution in first)


def test_minimum_history_fallback_and_fail_closed_inputs_are_explicit() -> None:
    adapter = BigLotto2BetHedgingAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)

    assert adapter.get_bets(_history(1), LotteryType.BIG_LOTTO) == DONOR_GOLDENS[("cycle", 1)]
    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_portfolio_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)

    assert len(catalog) == 118
    assert descriptor.strategy_id == BigLotto2BetHedgingAdapter.strategy_id
    assert descriptor.strategy_name == BigLotto2BetHedgingAdapter.strategy_name
    assert descriptor.version == BigLotto2BetHedgingAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 2
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_2bet_hedging:"
        "BigLotto2BetHedgingAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "07a3aa4550743a967e195d4e1a40d535e368f331e890247f1cd7c5e0e50e1b9b"
        in descriptor.provenance
    )
    assert "legacy_symbol:main_default_standard_mode" in descriptor.provenance
    assert "donor_execution:REVIVED_DB_LOADER_AND_REPORTING_ISOLATED" in (
        descriptor.provenance
    )
    assert "live_db_required:NO" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLotto2BetHedgingAdapter
    )


def test_production_portfolio_path_is_reachable_and_single_path_rejects_identity() -> None:
    request = GenerateOneBetInput(
        STRATEGY_ID,
        LotteryType.BIG_LOTTO,
        _history(50),
    )
    portfolio = build_production_generate_portfolio().execute(request)
    single = build_production_generate_one_bet().execute(request)

    assert portfolio.status is GeneratePortfolioStatus.OK
    assert portfolio.numbers == DONOR_GOLDENS[("cycle", 50)]
    assert single.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert single.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert single.numbers is None


def test_production_generation_never_opens_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Big Lotto 2-bet hedge must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, _history(50))
    )
    assert result.status is GeneratePortfolioStatus.OK
