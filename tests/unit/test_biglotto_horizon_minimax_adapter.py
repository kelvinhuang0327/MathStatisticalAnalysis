"""Parity and target-native contract tests for Horizon Minimax R1."""

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
    run_cli_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_horizon_minimax import (
    BigLottoHorizonMinimaxDisagreementAdapter,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "b649_new_horizon_minimax_disagreement_r1"


def _cyclic_history(length: int) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"history-{index + 1}",
            numbers=tuple(
                sorted((((index + 7 * offset) % 49) + 1) for offset in range(6))
            ),
        )
        for index in range(length)
    )


def _block_history(*, reversed_blocks: bool = False) -> tuple[CausalDrawRow, ...]:
    low = (1, 2, 3, 4, 5, 6)
    high = (44, 45, 46, 47, 48, 49)
    blocks = (high, low) if reversed_blocks else (low, high)
    numbers = (blocks[0],) * 100 + (blocks[1],) * 100
    return tuple(
        CausalDrawRow(str(index + 1), f"history-{index + 1}", ticket)
        for index, ticket in enumerate(numbers)
    )


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (
            200,
            ((1, 2, 3, 4, 8, 11), (3, 4, 10, 22, 23, 29)),
        ),
        (
            201,
            ((1, 2, 3, 4, 5, 12), (4, 5, 11, 22, 23, 24)),
        ),
        (
            250,
            ((1, 2, 3, 4, 5, 12), (4, 5, 11, 22, 23, 24)),
        ),
    ],
)
def test_sealed_research_parity_goldens(
    length: int,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    adapter = BigLottoHorizonMinimaxDisagreementAdapter()

    first = adapter.get_bets(_cyclic_history(length), LotteryType.BIG_LOTTO)
    second = adapter.get_bets(_cyclic_history(length), LotteryType.BIG_LOTTO)

    assert first == second == expected
    assert len(first) == 2
    assert len(set(first[0]) & set(first[1])) <= 2


def test_tail_horizons_are_oldest_first_and_full_prefix_is_not_truncated() -> None:
    adapter = BigLottoHorizonMinimaxDisagreementAdapter()

    forward = adapter.get_bets(_block_history(), LotteryType.BIG_LOTTO)
    reversed_blocks = adapter.get_bets(
        _block_history(reversed_blocks=True),
        LotteryType.BIG_LOTTO,
    )

    assert forward == ((1, 2, 3, 44, 45, 46), (1, 2, 4, 5, 6, 7))
    assert reversed_blocks == ((1, 2, 3, 4, 5, 6), (44, 45, 46, 47, 48, 49))
    assert forward != reversed_blocks


def test_minimum_history_and_lottery_type_fail_closed() -> None:
    adapter = BigLottoHorizonMinimaxDisagreementAdapter()

    with pytest.raises(InsufficientHistory, match="needs 200 draws, got 199"):
        adapter.get_bets(_cyclic_history(199), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(_cyclic_history(200), LotteryType.POWER_LOTTO)


def test_catalog_registry_and_response_path_preserve_one_two_ticket_identity() -> None:
    catalog = production_catalog()
    descriptor = catalog.get(STRATEGY_ID)

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
    ) == (
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_id,
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_name,
        BigLottoHorizonMinimaxDisagreementAdapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        BigLottoHorizonMinimaxDisagreementAdapter.min_history,
        ResponseShape.PORTFOLIO,
        2,
    )
    assert (
        ExecutableRegistry(catalog).load_adapter(STRATEGY_ID)
        is BigLottoHorizonMinimaxDisagreementAdapter
    )
    assert "evidence_status:HISTORICAL_RESEARCH_ONLY" in descriptor.provenance
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance
    assert "predictive_advantage_claimed:NO" in descriptor.provenance

    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_cyclic_history(200),
    )
    portfolio = build_production_generate_portfolio().execute(request)
    assert portfolio.status is GeneratePortfolioStatus.OK
    assert portfolio.numbers == ((1, 2, 3, 4, 8, 11), (3, 4, 10, 22, 23, 29))

    one_bet = build_production_generate_one_bet().execute(request)
    assert one_bet.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert one_bet.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert one_bet.numbers is None


def test_existing_cli_portfolio_vertical_returns_all_tickets_and_seed_is_metadata() -> None:
    history_json = json.dumps(
        [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in _cyclic_history(200)
        ]
    )

    first_text, first_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=7,
        history_json=history_json,
    )
    second_text, second_ok = run_cli_generate_portfolio(
        strategy_id=STRATEGY_ID,
        seed=999,
        history_json=history_json,
    )
    first = json.loads(first_text)
    second = json.loads(second_text)

    assert first_ok is second_ok is True
    assert first["numbers"] == second["numbers"] == [
        [1, 2, 3, 4, 8, 11],
        [3, 4, 10, 22, 23, 29],
    ]
    assert first["seed"] == 7
    assert second["seed"] == 999
