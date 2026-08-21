"""Contract tests for the DAILY_539 native-strategy batch 01 adapter
(``acb_single_539``).

This wraps ``daily539_single_legacy.py``'s already-defined ``_acb_predict``
producer (already exercised through its own hand-rolled
``Daily539AcbSingleAdapter`` by ``tools/run_daily539_t539_wave1.py``); the
tests here focus on the new wrapper's own contract: it must reach the
identical producer byte-for-byte through the real ``BetAdapter`` base, and
be reachable from the production catalog for the first time DAILY_539 has
ever had a catalog entry.
"""

# pyright: reportPrivateUsage=false
# (reachability check reads the registry's internal adapter map directly,
# the same established pattern test_biglotto_batch16_adapters.py already
# uses for the identical purpose)

from __future__ import annotations

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.daily539_batch01 import Daily539AcbSingleCatalogAdapter
from lottolab.strategies.adapters.daily539_single_legacy import _acb_predict
from lottolab.strategies.catalog import production_catalog

STRATEGY_ID = "acb_single_539"


def _row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 39) + 1 for offset in range(5)))
    assert len(set(numbers)) == 5
    return CausalDrawRow(
        draw=f"db01-{index:05d}",
        date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(count: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(index) for index in range(count))


def test_wrapper_matches_underlying_producer_exactly() -> None:
    history = _history(150)
    expected = _acb_predict(history)

    ticket, special = Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)

    assert ticket == expected
    assert special is None


def test_native_output_is_one_legal_five_of_39_ticket() -> None:
    history = _history(150)
    ticket, special = Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert len(ticket) == 5
    assert len(set(ticket)) == 5
    assert all(1 <= number <= 39 for number in ticket)
    assert ticket == tuple(sorted(ticket))
    assert special is None


def test_repeated_execution_byte_equality() -> None:
    history = _history(150)
    first = Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)
    second = Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert first == second


def test_rejects_insufficient_history() -> None:
    history = _history(99)
    with pytest.raises(InsufficientHistory):
        Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)


def test_accepts_exactly_min_history() -> None:
    history = _history(100)
    ticket, _special = Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.DAILY_539)
    assert len(ticket) == 5


def test_rejects_wrong_lottery_type() -> None:
    history = _history(150)
    with pytest.raises(UnsupportedLotteryType):
        Daily539AcbSingleCatalogAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)


def test_production_catalog_declares_expected_shape() -> None:
    descriptor = production_catalog().get(STRATEGY_ID)
    assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
    assert descriptor.executable is True
    assert descriptor.min_history == 100
    assert descriptor.lottery_types == (LotteryType.DAILY_539,)


def test_production_catalog_appends_daily539_batch01_last_in_current_main_prefix() -> None:
    """This is the first DAILY_539 descriptor the production catalog has
    ever had, appended directly after the three-strategy POWER_LOTTO batch
    01 (``power_lead_lag_2bet``) and last in the preserved current-main
    prefix; the legacy-mechanism publication appends after that prefix."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    current_main_prefix = all_ids[:92]
    assert current_main_prefix[-1] == STRATEGY_ID
    assert current_main_prefix[-2] == "power_lead_lag_2bet"
    assert all_ids.count(STRATEGY_ID) == 1


def test_strategy_is_reachable_only_through_the_single_bet_response_path() -> None:
    use_case = build_production_generate_one_bet()
    assert STRATEGY_ID in use_case._adapters


def test_generate_one_bet_returns_legal_result() -> None:
    use_case = build_production_generate_one_bet()
    history = _history(150)
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.DAILY_539,
            history=history,
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == _acb_predict(history)
    assert result.special_number is None
