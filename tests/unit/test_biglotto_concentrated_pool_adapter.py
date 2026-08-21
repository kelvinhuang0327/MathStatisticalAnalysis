"""Exact donor parity and runtime tests for concentrated-pool intake."""

from __future__ import annotations

from typing import cast

import pytest

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    CONCENTRATED_POOL_METHOD_ID,
    LegacyHistoryNativeWave2Request,
    generate_legacy_history_native_wave2_portfolio,
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
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_concentrated_pool import (
    BigLottoConcentratedPoolPredictorAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__concentrated_pool_predictor__a03b90705749"


def _wave_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"cp-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave_history(count: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave_row(index) for index in range(count))


def _donor_tickets(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    """Execute the preserved in-repo donor reconstruction as the parity oracle."""

    result = generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=CONCENTRATED_POOL_METHOD_ID,
            target_draw_number="parity-target",
            history=tuple(
                LegacyHistoryDraw(
                    draw_number=row.draw,
                    numbers=cast(Ticket, row.numbers),
                )
                for row in history
            ),
        )
    )
    return result.tickets


@pytest.mark.parametrize("history_length", (1, 2, 10, 30, 50, 100, 150))
def test_adapter_matches_preserved_wave2_donor_on_causal_histories(
    history_length: int,
) -> None:
    adapter = BigLottoConcentratedPoolPredictorAdapter()
    history = _wave_history(history_length)
    expected = _donor_tickets(history)

    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == expected
    assert len(expected) == 2
    for ticket in expected:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)


def test_prediction_for_draw_n_ignores_later_history_suffix() -> None:
    adapter = BigLottoConcentratedPoolPredictorAdapter()
    prefix = _wave_history(40)
    with_future = prefix + _wave_history(80)[40:]

    prediction_for_n = adapter.get_bets(prefix, LotteryType.BIG_LOTTO)
    look_ahead_call = adapter.get_bets(with_future, LotteryType.BIG_LOTTO)

    assert prediction_for_n == _donor_tickets(prefix)
    assert look_ahead_call == _donor_tickets(with_future)
    assert prediction_for_n != look_ahead_call
    assert adapter.get_bets(prefix, LotteryType.BIG_LOTTO) == prediction_for_n


def test_native_output_is_two_legal_tickets_and_failures_close() -> None:
    adapter = BigLottoConcentratedPoolPredictorAdapter()
    history = _wave_history(25)
    expected = _donor_tickets(history)
    executions = adapter.get_bets_with_emission(history, LotteryType.BIG_LOTTO)

    assert tuple(execution.legal_main_numbers for execution in executions) == expected
    for execution in executions:
        assert execution.emitted_main_numbers == execution.legal_main_numbers
        assert len(execution.legal_main_numbers) == 6
        assert len(set(execution.legal_main_numbers)) == 6
        assert all(1 <= number <= 49 for number in execution.legal_main_numbers)

    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.POWER_LOTTO)
    with pytest.raises(InvalidOutput):
        adapter.get_bets("not-a-tuple", LotteryType.BIG_LOTTO)  # type: ignore[arg-type]
    with pytest.raises(InvalidOutput):
        adapter.get_bets(
            (CausalDrawRow("bad", "2020-01-01", (1, 2, 3, 4, 5, 99)),),
            LotteryType.BIG_LOTTO,
        )


def test_catalog_registry_and_production_portfolio_path_match_donor() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    adapter = BigLottoConcentratedPoolPredictorAdapter()

    assert (
        descriptor.strategy_id,
        descriptor.strategy_name,
        descriptor.version,
        descriptor.lottery_types,
        descriptor.lifecycle_status,
        descriptor.executable,
        descriptor.min_history,
        descriptor.response_shape,
        descriptor.native_ticket_count,
        descriptor.adapter_path,
    ) == (
        adapter.strategy_id,
        adapter.strategy_name,
        adapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        adapter.min_history,
        ResponseShape.PORTFOLIO,
        2,
        "lottolab.strategies.adapters.biglotto_concentrated_pool:"
        "BigLottoConcentratedPoolPredictorAdapter",
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoConcentratedPoolPredictorAdapter
    )
    assert "legacy_source:lottery_api/models/concentrated_pool_predictor.py" in (
        descriptor.provenance
    )
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance
    assert "predictive_advantage_claimed:NO" in descriptor.provenance

    history = _wave_history(25)
    expected = _donor_tickets(history)
    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=history,
    )
    result = build_production_generate_portfolio().execute(request)
    one_bet = build_production_generate_one_bet().execute(request)

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == expected
    assert one_bet.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert one_bet.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert one_bet.numbers is None


def test_production_catalog_preserves_concentrated_pool_append_position() -> None:
    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 101
    assert all_ids[-9] == STRATEGY_ID
    assert all_ids[:-9].count(STRATEGY_ID) == 0
    assert all_ids[-10] == "acb_single_539"
    assert all_ids[-8] == "legacy_biglotto__constraint_filter_predictor__3a85b3995002"
    assert all_ids[-7] == "legacy_biglotto__predict_biglotto_apriori__cda690ae84c2"
    assert all_ids[-6] == "legacy_biglotto__smart_multi_bet__613c62c1f192"
    assert all_ids[-5] == "legacy_biglotto__anti_consensus_strategy__a454ddd26cef"
    assert all_ids[-4] == "legacy_biglotto__cooccurrence_graph__25fa2e473092"
    assert all_ids[-3] == "legacy_biglotto__backtest_radical_strategy__e54cc0812bc6"
    assert all_ids[-2] == "legacy_biglotto__power_fourier_rhythm__cb75e72e4c94"
    assert all_ids[-1] == ("legacy_biglotto__backtest_big_lotto_orthogonal_5bet__c4dff46c5a5e")
