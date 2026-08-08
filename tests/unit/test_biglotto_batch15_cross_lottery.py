"""Contract tests for the BIGLOTTO68 cross-lottery Batch-15 closure."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
import random
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_batch15 as native_batch15
from lottolab.strategies.adapters import powerlotto_wave6
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    SourceNativePortfolioClosure,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_batch15_cross_lottery_core import (
    TargetGameSpec,
    cold_hunter_predict,
    dm_dms_tickets,
    dms_solo_ticket,
    gap_pressure_predict,
    moderate_rank_predict,
    pure_cold_predict,
    rebound_aware_predict,
    short_window_deviation_predict,
    zone_momentum_candidate,
)
from lottolab.strategies.adapters.daily539_biglotto_batch15 import (
    DAILY539_BATCH15_ADAPTERS,
    Daily539Batch15AdapterClass,
    Daily539BigLottoColdHunterAdapter,
    Daily539BigLottoDmDmsAdapter,
)
from lottolab.strategies.adapters.powerlotto_wave1 import (
    P638HistoryRow,
    P638StrategySpec,
    P638TicketSet,
)
from lottolab.strategies.adapters.powerlotto_wave6 import WAVE6_STRATEGIES
from lottolab.strategies.powerlotto_second_zone import second_zone_predict

_BATCH15_IDS = (
    "t539_biglotto_cold_hunter_1bet",
    "t539_biglotto_short_window_deviation_1bet",
    "t539_biglotto_rebound_aware_1bet",
    "t539_biglotto_zone_momentum_1bet",
    "t539_biglotto_pure_cold_1bet",
    "t539_biglotto_moderate_rank_1bet",
    "t539_biglotto_gap_pressure_1bet",
    "t539_biglotto_dm_dms_2bet",
    "t539_biglotto_dms_1bet",
)


@pytest.fixture(scope="module")
def t539_history() -> tuple[CausalDrawRow, ...]:
    rng = random.Random("biglotto68-to-t539")
    return tuple(
        CausalDrawRow(
            draw=str(99000001 + index),
            date=f"2025-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 40), 5))),
        )
        for index in range(180)
    )


@pytest.fixture(scope="module")
def p638_history() -> tuple[P638HistoryRow, ...]:
    rng = random.Random("biglotto68-to-p638")
    return tuple(
        P638HistoryRow(
            draw=str(99100001 + index),
            date=f"2025-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 39), 6))),
            second_number=(index % 8) + 1,
        )
        for index in range(180)
    )


def test_batch15_identity_order_and_native_counts_are_fixed() -> None:
    assert tuple(adapter.strategy_id for adapter in DAILY539_BATCH15_ADAPTERS) == _BATCH15_IDS
    assert tuple(
        adapter.native_ticket_count for adapter in DAILY539_BATCH15_ADAPTERS
    ) == (1, 1, 1, 1, 1, 1, 1, 2, 1)
    assert tuple(spec.strategy_id for spec in WAVE6_STRATEGIES) == tuple(
        strategy_id.replace("t539_", "power_", 1) for strategy_id in _BATCH15_IDS
    )


@pytest.mark.parametrize("adapter_class", DAILY539_BATCH15_ADAPTERS, ids=lambda cls: cls.__name__)
def test_t539_adapters_are_deterministic_and_target_native(
    adapter_class: Daily539Batch15AdapterClass,
    t539_history: tuple[CausalDrawRow, ...],
) -> None:
    adapter = adapter_class()
    random.seed(1)
    if isinstance(adapter, Daily539BigLottoDmDmsAdapter):
        first = adapter.get_bets(t539_history, LotteryType.DAILY_539)
    else:
        first = (adapter.get_one_bet(t539_history, LotteryType.DAILY_539)[0],)
    random.seed(2)
    if isinstance(adapter, Daily539BigLottoDmDmsAdapter):
        repeated = adapter.get_bets(t539_history, LotteryType.DAILY_539)
    else:
        repeated = (adapter.get_one_bet(t539_history, LotteryType.DAILY_539)[0],)
    assert first == repeated
    assert len(first) == adapter.native_ticket_count
    assert all(
        len(ticket) == 5
        and len(set(ticket)) == 5
        and all(type(number) is int and 1 <= number <= 39 for number in ticket)
        for ticket in first
    )


def test_t539_adapters_reject_power_lotto_and_malformed_history(
    t539_history: tuple[CausalDrawRow, ...],
) -> None:
    adapter = Daily539BigLottoColdHunterAdapter()
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_one_bet(t539_history, LotteryType.POWER_LOTTO)
    malformed = (*t539_history[:-1], CausalDrawRow("bad", "2025-01-01", (1, 2, 3, 4, 40)))
    with pytest.raises(InvalidOutput):
        adapter.get_one_bet(malformed, LotteryType.DAILY_539)


def _p638_outcome(
    spec: P638StrategySpec,
    history: tuple[P638HistoryRow, ...],
) -> tuple[str, P638TicketSet | int]:
    try:
        return "COMPLETE", spec.predict_tickets(history, LotteryType.POWER_LOTTO)
    except SourceNativePortfolioClosure as exc:
        assert exc.actual_ticket_count in spec.source_native_closure_ticket_counts
        return "CLOSURE", exc.actual_ticket_count


@pytest.mark.parametrize("spec", WAVE6_STRATEGIES, ids=lambda spec: spec.strategy_id)
def test_p638_wave6_is_deterministic_and_second_zone_stays_ssot(
    spec: P638StrategySpec,
    p638_history: tuple[P638HistoryRow, ...],
) -> None:
    random.seed(11)
    first_status, first_value = _p638_outcome(spec, p638_history)
    random.seed(29)
    second_status, second_value = _p638_outcome(spec, p638_history)
    assert (first_status, first_value) == (second_status, second_value)
    if first_status == "CLOSURE":
        return

    tickets = cast(P638TicketSet, first_value)
    assert len(tickets) == spec.native_ticket_count
    expected_second_zone = second_zone_predict(
        [{"special": row.second_number} for row in p638_history]
    )
    for first_zone, second_zone in tickets:
        assert len(first_zone) == 6
        assert len(set(first_zone)) == 6
        assert all(type(number) is int and 1 <= number <= 38 for number in first_zone)
        assert second_zone == expected_second_zone


def test_wave6_target_native_module_does_not_import_native_biglotto_adapter() -> None:
    source = inspect.getsource(powerlotto_wave6)
    assert "from lottolab.strategies.adapters.biglotto_batch15 import" not in source
    assert "lottolab.application" not in source
    assert "lottolab.infrastructure" not in source
    assert "lottolab.interfaces" not in source


@pytest.mark.parametrize("length", (1, 12, 50, 180))
def test_shared_core_preserves_batch15_donor_control_flow_at_49_numbers(length: int) -> None:
    game = TargetGameSpec(LotteryType.BIG_LOTTO, maximum=49, pick_count=6)
    rng = random.Random(f"biglotto68-donor-parity-{length}")
    rows = tuple(
        CausalDrawRow(
            draw=str(99200001 + index),
            date="2025-01-01",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(length)
    )
    numbers = tuple(row.numbers for row in rows)
    for generic, donor in (
        (cold_hunter_predict, native_batch15._cold_hunter_predict),
        (short_window_deviation_predict, native_batch15._short_window_deviation_predict),
        (rebound_aware_predict, native_batch15._rebound_aware_predict),
        (pure_cold_predict, native_batch15._pure_cold_predict),
        (moderate_rank_predict, native_batch15._moderate_rank_predict),
        (gap_pressure_predict, native_batch15._gap_pressure_predict),
    ):
        assert generic(numbers, game) == donor(rows)
    try:
        donor_zone = native_batch15._zone_momentum_predict(rows)
    except ValueError:
        assert len(zone_momentum_candidate(numbers, game)) != 6
    else:
        assert zone_momentum_candidate(numbers, game) == donor_zone
    assert dm_dms_tickets(numbers, game) == native_batch15._dm_dms_tickets(rows)
    assert dms_solo_ticket(numbers, game) == native_batch15._dms_solo_ticket(rows)
