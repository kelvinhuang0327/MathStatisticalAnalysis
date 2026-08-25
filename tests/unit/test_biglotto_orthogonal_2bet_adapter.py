"""Executable old/new parity for the legacy Orthogonal 2-Bet donor."""

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
from lottolab.strategies.adapters import BigLottoOrthogonal2BetAdapter
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__orthogonal_2bet_optimizer__aa51b0e5e4a4"


def _history(length: int, mode: str = "cycle") -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(length):
        if mode == "cycle":
            numbers = tuple(
                sorted({((index * 7 + offset * 5) % 49) + 1 for offset in range(6)})
            )
        elif mode == "boundary":
            numbers = (1, 2, 3, 4, 5, 49 if index % 2 == 0 else 48)
        else:
            numbers = tuple(
                sorted({((index + offset * 8) % 49) + 1 for offset in range(6)})
            )
        rows.append(
            CausalDrawRow(
                draw=f"orthogonal-2bet-{index}",
                date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                numbers=numbers,
            )
        )
    return tuple(rows)


DONOR_GOLDENS: dict[tuple[str, int], tuple[tuple[int, ...], ...]] = {
    ("cycle", 1): ((1, 6, 11, 16, 21, 26), (2, 3, 4, 5, 7, 8)),
    ("cycle", 2): ((8, 13, 18, 23, 28, 33), (2, 3, 4, 5, 7, 9)),
    ("cycle", 49): ((2, 4, 7, 9, 14, 19), (1, 6, 8, 11, 13, 16)),
    ("cycle", 50): ((1, 6, 11, 16, 21, 26), (8, 13, 15, 18, 20, 23)),
    ("cycle", 51): ((8, 13, 18, 23, 28, 33), (15, 20, 22, 25, 27, 30)),
    ("cycle", 500): ((15, 20, 25, 30, 35, 40), (1, 5, 22, 27, 29, 32)),
    ("cycle", 501): ((22, 27, 32, 37, 42, 47), (1, 2, 4, 5, 7, 12)),
    ("cycle", 750): ((1, 6, 11, 16, 21, 26), (8, 13, 15, 18, 20, 23)),
    ("boundary", 80): ((1, 2, 3, 4, 5, 48), (6, 7, 8, 9, 10, 11)),
    ("tie", 80): ((6, 14, 22, 31, 39, 47), (1, 9, 17, 25, 26, 33)),
}


@pytest.mark.parametrize(("mode", "length"), tuple(DONOR_GOLDENS))
def test_matches_revived_donor_golden(mode: str, length: int) -> None:
    assert BigLottoOrthogonal2BetAdapter().get_bets(
        _history(length, mode), LotteryType.BIG_LOTTO
    ) == DONOR_GOLDENS[(mode, length)]


def test_portfolio_emission_preserves_two_ticket_order_and_legality() -> None:
    adapter = BigLottoOrthogonal2BetAdapter()
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
    assert set(first[0].legal_main_numbers).isdisjoint(first[1].legal_main_numbers)


def test_minimum_history_and_fail_closed_inputs_are_explicit() -> None:
    adapter = BigLottoOrthogonal2BetAdapter()
    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)

    invalid = (CausalDrawRow("bad", "bad", (1, 1, 2, 3, 4, 5)),)
    with pytest.raises(InvalidOutput):
        adapter.get_bets(invalid, LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(1), LotteryType.DAILY_539)


def test_catalog_and_registry_add_exactly_one_online_portfolio_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)

    assert len(catalog) == 120
    assert descriptor.strategy_id == BigLottoOrthogonal2BetAdapter.strategy_id
    assert descriptor.strategy_name == BigLottoOrthogonal2BetAdapter.strategy_name
    assert descriptor.version == BigLottoOrthogonal2BetAdapter.strategy_version
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.lifecycle_status is LifecycleStatus.ONLINE
    assert descriptor.executable is True
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 2
    assert descriptor.min_history == 1
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_orthogonal_2bet:"
        "BigLottoOrthogonal2BetAdapter"
    )
    assert (
        "legacy_source_sha256:"
        "aa51b0e5e4a400c189aa87c4e478f7b5429223ea1ec81dea13ebebe2b1df42f1"
        in descriptor.provenance
    )
    assert "legacy_symbol:Orthogonal2BetOptimizer.predict" in descriptor.provenance
    assert "donor_execution:REVIVED_WITH_UNUSED_NUMPY_AND_ENGINE_ISOLATED" in (
        descriptor.provenance
    )
    assert "live_db_required:NO" in descriptor.provenance
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoOrthogonal2BetAdapter
    )


def test_production_portfolio_path_is_reachable_and_single_path_rejects_identity() -> None:
    history = _history(50)
    request = GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, history)

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
        raise AssertionError("Orthogonal 2-Bet must not open a database")

    monkeypatch.setattr(sqlite3, "connect", _forbidden_connect)
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(STRATEGY_ID, LotteryType.BIG_LOTTO, _history(50))
    )

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == DONOR_GOLDENS[("cycle", 50)]
