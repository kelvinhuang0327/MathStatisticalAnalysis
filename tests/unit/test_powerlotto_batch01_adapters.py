"""Contract tests for the POWER_LOTTO native-strategy batch 01 adapters
(``zonal_entropy_2bet``, ``power_apriori_2bet``, ``power_lead_lag_2bet``).

These wrap already-tested Wave 1/Wave 2 predictor functions (see
``test_powerlotto_adapters_wave1.py``/``test_powerlotto_adapters_wave2.py``
for their own algorithm-level verification); the tests here focus on the
wrapper's own contract: it must reach the identical already-tested predictor
byte-for-byte through the ``CausalDrawRow`` -> ``P638HistoryRow`` boundary,
satisfy ``PortfolioBetAdapter``, and be reachable from the production
catalog.
"""

# pyright: reportPrivateUsage=false
# (reachability check reads the registry's internal adapter map directly,
# the same established pattern test_biglotto_batch16_adapters.py already
# uses for the identical purpose)

from __future__ import annotations

from collections.abc import Callable

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.powerlotto_batch01 import (
    PowerLottoApriori2BetAdapter,
    PowerLottoLeadLag2BetAdapter,
    PowerLottoZonalEntropy2BetAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638FirstZoneTicketSet,
    P638HistoryRow,
    _zonal_entropy_tickets,
)
from lottolab.strategies.adapters.powerlotto_wave2 import _apriori_tickets, _lead_lag_tickets
from lottolab.strategies.catalog import production_catalog

ZONAL_ENTROPY_ID = "zonal_entropy_2bet"
APRIORI_ID = "power_apriori_2bet"
LEAD_LAG_ID = "power_lead_lag_2bet"

Predictor = Callable[[tuple[P638HistoryRow, ...]], P638FirstZoneTicketSet]
AdapterCase = tuple[type[PortfolioBetAdapter], str, int, Predictor]


def _row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 38) + 1 for offset in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"pb01-{index:05d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(count: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index) for index in range(count))


def _as_p638_history(history: tuple[CausalDrawRow, ...]) -> tuple[P638HistoryRow, ...]:
    return tuple(
        P638HistoryRow(draw=row.draw, date=row.date, numbers=row.numbers, second_number=1)
        for row in history
    )


ADAPTERS: tuple[AdapterCase, ...] = (
    (PowerLottoZonalEntropy2BetAdapter, ZONAL_ENTROPY_ID, 30, _zonal_entropy_tickets),
    (PowerLottoApriori2BetAdapter, APRIORI_ID, 10, _apriori_tickets),
    (PowerLottoLeadLag2BetAdapter, LEAD_LAG_ID, 10, _lead_lag_tickets),
)


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_wrapper_matches_underlying_predictor_exactly(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(120)
    expected = predictor(_as_p638_history(history))

    actual = adapter_class().get_bets(history, LotteryType.POWER_LOTTO)

    assert actual == expected


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_native_shape_and_special_number_is_none(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(120)
    executions = adapter_class().get_bets_with_emission(history, LotteryType.POWER_LOTTO)

    assert len(executions) == 2
    for execution in executions:
        assert len(execution.legal_main_numbers) == 6
        assert len(set(execution.legal_main_numbers)) == 6
        assert all(1 <= number <= 38 for number in execution.legal_main_numbers)
        assert execution.legal_main_numbers == tuple(sorted(execution.legal_main_numbers))
        assert execution.special_number is None


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(150)
    first = adapter_class().get_bets(history, LotteryType.POWER_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.POWER_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_rejects_insufficient_history(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(min_history - 1)
    with pytest.raises(InsufficientHistory):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_accepts_exactly_min_history(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(min_history)
    tickets = adapter_class().get_bets(history, LotteryType.POWER_LOTTO)
    assert len(tickets) == 2


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    history = _history(120)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_production_catalog_declares_expected_shape(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    descriptor = production_catalog().get(strategy_id)
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 2
    assert descriptor.executable is True
    assert descriptor.min_history == min_history
    assert descriptor.lottery_types == (LotteryType.POWER_LOTTO,)


def test_production_catalog_appends_powerlotto_batch01_before_wave2() -> None:
    """This batch adds exactly three POWER_LOTTO descriptors, appended
    directly after the BIG_LOTTO batch 18 pair and directly before the
    DAILY_539 batch 01 descriptor and before the Wave 2 catalog block -- the
    first three POWER_LOTTO entries the production catalog has ever had."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    pre_wave2 = all_ids[:92]
    assert pre_wave2[-4] == ZONAL_ENTROPY_ID
    assert pre_wave2[-3] == APRIORI_ID
    assert pre_wave2[-2] == LEAD_LAG_ID
    assert all_ids.count(ZONAL_ENTROPY_ID) == 1
    assert all_ids.count(APRIORI_ID) == 1
    assert all_ids.count(LEAD_LAG_ID) == 1


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_strategy_is_reachable_only_through_the_portfolio_response_path(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    portfolio = build_production_generate_portfolio()
    assert strategy_id in portfolio._adapters


@pytest.mark.parametrize("adapter_class,strategy_id,min_history,predictor", ADAPTERS)
def test_generate_portfolio_returns_complete_native_ticket_set(
    adapter_class: type[PortfolioBetAdapter],
    strategy_id: str,
    min_history: int,
    predictor: Predictor,
) -> None:
    use_case = build_production_generate_portfolio()
    history = _history(120)
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.POWER_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == predictor(_as_p638_history(history))
