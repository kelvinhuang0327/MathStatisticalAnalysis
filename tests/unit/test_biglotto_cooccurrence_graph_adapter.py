"""Contract and frozen-oracle parity tests for the B649 graph adapter."""

from __future__ import annotations

import random

import pytest

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_history_native_portfolios_wave2 import (
    COOCCURRENCE_GRAPH_METHOD_ID,
    LegacyHistoryNativeWave2Request,
    generate_legacy_history_native_wave2_portfolio,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_cooccurrence_graph import (
    BigLottoCooccurrenceGraphAdapter,
    _target_after_causal_cutoff,
)
from lottolab.strategies.catalog import production_catalog

STRATEGY_ID = "legacy_biglotto__cooccurrence_graph__25fa2e473092"


def _history(count: int) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(20260728)
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(count)
    )


def _oracle(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    return generate_legacy_history_native_wave2_portfolio(
        LegacyHistoryNativeWave2Request(
            legacy_method_id=COOCCURRENCE_GRAPH_METHOD_ID,
            target_draw_number=_target_after_causal_cutoff(history),
            history=tuple(
                LegacyHistoryDraw(draw_number=row.draw, numbers=row.numbers)
                for row in history
            ),
        )
    ).tickets


@pytest.mark.parametrize("history_count", (100, 120, 300))
def test_adapter_matches_frozen_oracle_for_causal_histories(history_count: int) -> None:
    history = _history(history_count)
    adapter = BigLottoCooccurrenceGraphAdapter()

    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == _oracle(history)
    assert _target_after_causal_cutoff(history) not in {row.draw for row in history}


def test_adapter_is_deterministic_and_has_legal_four_ticket_output() -> None:
    history = _history(120)
    adapter = BigLottoCooccurrenceGraphAdapter()

    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)

    assert first == second
    assert len(first) == 4
    assert all(len(ticket) == 6 for ticket in first)
    assert all(ticket == tuple(sorted(ticket)) for ticket in first)
    assert all(len(set(ticket)) == 6 for ticket in first)
    assert all(all(1 <= number <= 49 for number in ticket) for ticket in first)


def test_adapter_enforces_biglotto_only_and_causal_history_gate() -> None:
    adapter = BigLottoCooccurrenceGraphAdapter()

    with pytest.raises(InsufficientHistory, match="needs 100 draws"):
        adapter.get_bets(_history(99), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_history(100), LotteryType.DAILY_539)


def test_catalog_and_portfolio_runtime_reach_exactly_one_identity() -> None:
    descriptor = production_catalog().get(STRATEGY_ID)
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.executable is True
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.min_history == 100
    assert descriptor.native_ticket_count == 4
    assert descriptor.adapter_path == (
        "lottolab.strategies.adapters.biglotto_cooccurrence_graph:"
        "BigLottoCooccurrenceGraphAdapter"
    )

    portfolio = build_production_generate_portfolio()
    result = portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(100),
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == BigLottoCooccurrenceGraphAdapter().get_bets(
        _history(100), LotteryType.BIG_LOTTO
    )

    one_bet = build_production_generate_one_bet()
    assert STRATEGY_ID not in one_bet._adapters
