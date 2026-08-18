# pyright: reportPrivateUsage=false

"""Parity and contract tests for BigLotto 5-bet TS3+Markov(w=30)+FreqOrt composite adapter."""

from __future__ import annotations

import json

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
    run_cli_generate_bet,
    run_cli_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_composite_quick_predict_5bet import (
    BigLottoCompositeQuickPredict5BetAdapter,
)
from lottolab.strategies.catalog import production_catalog

STRATEGY_ID = "legacy_composite__quick_predict_5bet_ts3_markov_freqort"


def _row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw using coprime stride 8."""
    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    return CausalDrawRow(
        draw=f"draw-{index}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_row(i) for i in range(n))


def test_catalog_registration() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)
    assert descriptor.strategy_id == STRATEGY_ID
    assert descriptor.strategy_name == "大樂透 Quick Predict 5注（TS3 + Markov + FreqOrt）"  # noqa: RUF001
    assert descriptor.version == "v0.1"
    assert descriptor.lottery_types == (LotteryType.BIG_LOTTO,)
    assert descriptor.executable is True
    assert descriptor.min_history == 500
    assert descriptor.response_shape is ResponseShape.PORTFOLIO
    assert descriptor.native_ticket_count == 5


def test_adapter_class_attributes() -> None:
    adapter = BigLottoCompositeQuickPredict5BetAdapter()
    assert adapter.strategy_id == STRATEGY_ID
    assert adapter.strategy_name == "大樂透 Quick Predict 5注（TS3 + Markov + FreqOrt）"  # noqa: RUF001
    assert adapter.strategy_version == "v0.1"
    assert adapter.min_history == 500
    assert adapter.supported_lottery_types == (LotteryType.BIG_LOTTO,)
    assert adapter.native_ticket_count == 5


def test_insufficient_history_fails_closed() -> None:
    adapter = BigLottoCompositeQuickPredict5BetAdapter()
    short_history = _history(499)
    with pytest.raises(InsufficientHistory):
        adapter.get_bets(short_history, LotteryType.BIG_LOTTO)


def test_unsupported_lottery_type_fails_closed() -> None:
    adapter = BigLottoCompositeQuickPredict5BetAdapter()
    history = _history(500)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.DAILY_539)


def test_valid_portfolio_generation() -> None:
    adapter = BigLottoCompositeQuickPredict5BetAdapter()
    history = _history(550)
    bets = adapter.get_bets(history, LotteryType.BIG_LOTTO)

    assert len(bets) == 5
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert ticket == tuple(sorted(ticket))
        assert all(1 <= num <= 49 for num in ticket)


def test_cross_ticket_orthogonality_and_exclusion() -> None:
    adapter = BigLottoCompositeQuickPredict5BetAdapter()
    history = _history(520)
    bets = adapter.get_bets(history, LotteryType.BIG_LOTTO)

    bet1, bet2, bet3, bet4, bet5 = bets

    # Ticket 2 excludes Ticket 1
    assert set(bet2).isdisjoint(set(bet1))

    # Ticket 3 excludes Tickets 1 and 2
    assert set(bet3).isdisjoint(set(bet1))
    assert set(bet3).isdisjoint(set(bet2))

    # Ticket 4 excludes Tickets 1, 2, 3
    assert set(bet4).isdisjoint(set(bet1))
    assert set(bet4).isdisjoint(set(bet2))
    assert set(bet4).isdisjoint(set(bet3))

    # Ticket 5 excludes Tickets 1, 2, 3, 4
    assert set(bet5).isdisjoint(set(bet1))
    assert set(bet5).isdisjoint(set(bet2))
    assert set(bet5).isdisjoint(set(bet3))
    assert set(bet5).isdisjoint(set(bet4))

    # Total unique numbers used across all 5 bets is exactly 5 * 6 = 30
    all_numbers = set(bet1) | set(bet2) | set(bet3) | set(bet4) | set(bet5)
    assert len(all_numbers) == 30


def test_use_case_portfolio_execution() -> None:
    gen_portfolio = build_production_generate_portfolio()
    history = _history(500)
    result = gen_portfolio.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers is not None
    assert len(result.numbers) == 5
    assert result.reason_code is None


def test_use_case_single_bet_fails_closed_for_portfolio() -> None:
    gen_single = build_production_generate_one_bet()
    history = _history(500)
    result = gen_single.execute(
        GenerateOneBetInput(
            strategy_id=STRATEGY_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_cli_portfolio_json_generation() -> None:
    history = _history(500)
    history_json = json.dumps(
        [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in history
        ]
    )
    rendered_json, ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=42,
        history_json=history_json,
    )
    assert ok is True
    parsed = json.loads(rendered_json)
    assert parsed["status"] == "OK"
    assert parsed["strategy_id"] == STRATEGY_ID
    assert parsed["lottery_type"] == "BIG_LOTTO"
    assert parsed["seed"] == 42
    assert len(parsed["numbers"]) == 5
    assert parsed["reason_code"] is None


def test_cli_single_bet_fails_closed_for_portfolio() -> None:
    history = _history(500)
    history_json = json.dumps(
        [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in history
        ]
    )
    rendered_json, ok = run_cli_generate_bet(
        strategy_id=STRATEGY_ID,
        seed=42,
        history_json=history_json,
    )
    assert ok is False
    parsed = json.loads(rendered_json)
    assert parsed["status"] == "WRONG_RESPONSE_PATH"
    assert parsed["reason_code"] == "STRATEGY_IS_PORTFOLIO"
    assert parsed["numbers"] is None
