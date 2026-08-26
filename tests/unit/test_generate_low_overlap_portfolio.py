"""Acceptance tests for the explicit low-overlap production application path."""

from __future__ import annotations

import sqlite3
from typing import cast
from unittest.mock import Mock

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBet,
    GenerateOneBetInput,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.application.use_cases.generate_low_overlap_portfolio import (
    GenerateLowOverlapPortfolio,
    GenerateLowOverlapPortfolioInput,
    GenerateLowOverlapPortfolioReason,
    GenerateLowOverlapPortfolioStatus,
    build_production_generate_low_overlap_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.strategies import ResponseShape
from lottolab.research import low_overlap_portfolio_constructor
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import production_catalog

STRATEGY_ID = "legacy_biglotto__frontend_zone_balance_strategy__6a016aa83b3e"


def _history(length: int = 20) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=f"frontend-zone-balance-{index}",
            date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(
                sorted(((index + step * 8) % 49) + 1 for step in range(6))
            ),
        )
        for index in range(length)
    )


def _one_bet_request(
    *,
    strategy_id: str = STRATEGY_ID,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
) -> GenerateOneBetInput:
    return GenerateOneBetInput(
        strategy_id=strategy_id,
        lottery_type=lottery_type,
        history=_history(),
    )


def _portfolio_request(
    *,
    strategy_id: str = STRATEGY_ID,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
    k: int = 5,
    construction_seed: int = 2026,
) -> GenerateLowOverlapPortfolioInput:
    return GenerateLowOverlapPortfolioInput(
        strategy_id=strategy_id,
        lottery_type=lottery_type,
        history=_history(),
        k=k,
        construction_seed=construction_seed,
    )


def _assert_legal_native_portfolio(
    tickets: tuple[tuple[int, ...], ...],
    expected_count: int,
) -> None:
    assert type(tickets) is tuple
    assert len(tickets) == expected_count
    assert len(set(tickets)) == expected_count
    for ticket in tickets:
        assert type(ticket) is tuple
        assert len(ticket) == BIG_LOTTO_RULE_CONTRACT.main_number_count
        assert ticket == tuple(sorted(ticket))
        assert all(
            BIG_LOTTO_RULE_CONTRACT.main_number_min
            <= number
            <= BIG_LOTTO_RULE_CONTRACT.main_number_max
            for number in ticket
        )
        assert len(set(ticket)) == len(ticket)


@pytest.fixture(scope="module")
def production_one_bet() -> GenerateOneBet:
    return build_production_generate_one_bet()


@pytest.fixture(scope="module")
def production_route() -> GenerateLowOverlapPortfolio:
    return build_production_generate_low_overlap_portfolio()


@pytest.mark.parametrize("k", (2, 3, 5, 10, 20))
def test_production_route_returns_exact_legal_unique_ladder_size(
    production_route: GenerateLowOverlapPortfolio,
    production_one_bet: GenerateOneBet,
    k: int,
) -> None:
    result = production_route.execute(_portfolio_request(k=k))

    assert result.status is GenerateLowOverlapPortfolioStatus.OK
    assert result.reason_code is None
    assert result.special_number is None
    assert result.numbers is not None
    _assert_legal_native_portfolio(result.numbers, k)

    base = production_one_bet.execute(_one_bet_request())
    assert base.status is GenerateOneBetStatus.OK
    assert base.numbers is not None
    assert result.numbers[0] == base.numbers


def test_fixed_construction_seed_is_deterministic(
    production_route: GenerateLowOverlapPortfolio,
) -> None:
    request = _portfolio_request(k=10, construction_seed=13579)

    assert production_route.execute(request) == production_route.execute(request)


def test_route_demonstrably_delegates_to_low_overlap_constructor(
    monkeypatch: pytest.MonkeyPatch,
    production_route: GenerateLowOverlapPortfolio,
) -> None:
    original = low_overlap_portfolio_constructor.build_low_overlap_portfolio
    wrapped = Mock(wraps=original)
    monkeypatch.setattr(
        low_overlap_portfolio_constructor,
        "build_low_overlap_portfolio",
        wrapped,
    )

    result = production_route.execute(_portfolio_request(k=5))

    assert result.status is GenerateLowOverlapPortfolioStatus.OK
    wrapped.assert_called_once()
    call = wrapped.call_args
    assert call is not None
    assert len(call.args[0]) >= 5
    assert call.args[1] == 5
    assert call.args[2] is BIG_LOTTO_RULE_CONTRACT
    assert call.kwargs["optional_scores"][0] == 1.0


def test_route_is_db_free(
    monkeypatch: pytest.MonkeyPatch,
    production_route: GenerateLowOverlapPortfolio,
) -> None:
    def fail_connect(*args: object, **kwargs: object) -> object:
        raise AssertionError("the production construction path must not use SQLite")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)

    result = production_route.execute(_portfolio_request(k=3))

    assert result.status is GenerateLowOverlapPortfolioStatus.OK


def test_k1_remains_the_existing_one_bet_path(
    production_route: GenerateLowOverlapPortfolio,
    production_one_bet: GenerateOneBet,
) -> None:
    one_bet = production_one_bet.execute(_one_bet_request())
    assert one_bet.status is GenerateOneBetStatus.OK
    assert one_bet.numbers == (1, 2, 3, 4, 9, 10)

    rejected = production_route.execute(_portfolio_request(k=1))

    assert rejected.status is GenerateLowOverlapPortfolioStatus.INVALID_REQUEST
    assert rejected.reason_code is GenerateLowOverlapPortfolioReason.INVALID_TICKET_COUNT


def test_incompatible_response_paths_fail_closed(
    production_route: GenerateLowOverlapPortfolio,
) -> None:
    catalog = production_catalog()
    portfolio_descriptor = next(
        descriptor
        for descriptor in catalog
        if descriptor.response_shape is ResponseShape.PORTFOLIO
    )

    low_overlap_result = production_route.execute(
        _portfolio_request(strategy_id=portfolio_descriptor.strategy_id)
    )
    assert low_overlap_result.status is GenerateLowOverlapPortfolioStatus.WRONG_RESPONSE_PATH
    assert (
        low_overlap_result.reason_code
        is GenerateLowOverlapPortfolioReason.STRATEGY_IS_PORTFOLIO
    )

    single_ticket_result = build_production_generate_portfolio().execute(
        _one_bet_request()
    )
    assert single_ticket_result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert single_ticket_result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO


def test_invalid_request_and_unsupported_lottery_fail_closed(
    production_route: GenerateLowOverlapPortfolio,
) -> None:
    invalid_seed = GenerateLowOverlapPortfolioInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_history(),
        k=5,
        construction_seed=cast(int, "not-an-integer"),
    )
    invalid_seed_result = production_route.execute(invalid_seed)
    assert invalid_seed_result.status is GenerateLowOverlapPortfolioStatus.INVALID_REQUEST
    assert (
        invalid_seed_result.reason_code
        is GenerateLowOverlapPortfolioReason.INVALID_CONSTRUCTION_SEED
    )

    unsupported_result = production_route.execute(
        _portfolio_request(lottery_type=LotteryType.DAILY_539)
    )
    assert unsupported_result.status is GenerateLowOverlapPortfolioStatus.STRATEGY_UNAVAILABLE
    assert (
        unsupported_result.reason_code
        is GenerateLowOverlapPortfolioReason.UNSUPPORTED_LOTTERY_TYPE
    )
