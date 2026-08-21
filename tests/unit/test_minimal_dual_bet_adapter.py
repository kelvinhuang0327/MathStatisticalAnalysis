"""Exact parity and runtime tests for the minimal dual-bet intake."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter

import pytest

from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GeneratePortfolioStatus,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, ResponseShape
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InsufficientHistory,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_minimal_dual_bet import (
    BigLottoMinimalDualBetStrategyAdapter,
    _minimal_dual_bets,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

STRATEGY_ID = "legacy_biglotto__minimal_dual_bet_strategy__3c9657df7ff4"


def _rows(tickets: tuple[tuple[int, ...], ...]) -> tuple[CausalDrawRow, ...]:
    return tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"history-{index + 1}",
            numbers=ticket,
        )
        for index, ticket in enumerate(tickets)
    )


def _weighted_history() -> tuple[CausalDrawRow, ...]:
    return _rows(
        ((1, 2, 3, 4, 5, 6),) * 20
        + ((26, 27, 28, 29, 30, 31),) * 10
        + ((14, 15, 16, 17, 18, 19),) * 5
    )


def _large_history() -> tuple[CausalDrawRow, ...]:
    prefix = ((1, 2, 3, 4, 5, 6),) * 50
    recent = (
        ((26, 27, 28, 29, 30, 31),) * 10
        + ((14, 15, 16, 17, 18, 19),) * 10
        + ((1, 2, 3, 4, 5, 6),) * 80
    )
    return _rows(prefix + recent)


def _donor_main_tickets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Independent test oracle transcribed from the frozen donor path."""

    source_history = tuple(reversed(history))
    recent = source_history[: min(100, len(source_history))]
    frequency: Counter[int] = Counter()
    for row in recent:
        frequency.update(row.numbers)

    sorted_numbers = sorted(
        range(1, 39),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )

    def select(candidates: tuple[int, ...]) -> tuple[int, ...]:
        selected: list[int] = []
        for start, end in ((1, 13), (14, 25), (26, 38)):
            zone_candidates = [
                number
                for number in candidates
                if start <= number <= end and number not in selected
            ]
            selected.extend(zone_candidates[:2])
        while len(selected) < 6 and candidates:
            remaining = [number for number in candidates if number not in selected]
            if not remaining:
                break
            selected.append(remaining[0])
        return tuple(selected[:6])

    bet1 = select(tuple(sorted_numbers[:20]))
    remaining = tuple(number for number in sorted_numbers if number not in bet1)
    bet2 = select(remaining[:20])
    return tuple(sorted(bet1)), tuple(sorted(bet2))


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        (
            _rows(((1, 2, 3, 4, 5, 6),)),
            ((1, 2, 3, 4, 14, 15), (5, 6, 7, 16, 17, 26)),
        ),
        (
            _weighted_history(),
            ((1, 2, 14, 15, 26, 27), (3, 4, 16, 17, 28, 29)),
        ),
    ],
)
def test_exact_donor_parity_for_minimum_and_intermediate_histories(
    history: tuple[CausalDrawRow, ...],
    expected: tuple[tuple[int, ...], ...],
) -> None:
    adapter = BigLottoMinimalDualBetStrategyAdapter()

    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == expected
    assert _minimal_dual_bets(history) == _donor_main_tickets(history) == expected


def test_exact_donor_parity_and_100_row_window_for_larger_history() -> None:
    adapter = BigLottoMinimalDualBetStrategyAdapter()
    history = _large_history()
    recent_only = history[-100:]

    assert len(history) == 150
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == _donor_main_tickets(history)
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == adapter.get_bets(
        recent_only, LotteryType.BIG_LOTTO
    )


def test_empty_donor_fallback_and_stable_tie_order_are_preserved_in_helper() -> None:
    assert _minimal_dual_bets(()) == (
        (1, 2, 3, 4, 14, 15),
        (5, 6, 7, 16, 17, 26),
    )


def test_native_output_is_two_legal_tickets_and_wrong_lottery_is_rejected() -> None:
    adapter = BigLottoMinimalDualBetStrategyAdapter()
    history = _weighted_history()
    executions = adapter.get_bets_with_emission(history, LotteryType.BIG_LOTTO)

    assert len(executions) == 2
    assert tuple(execution.legal_main_numbers for execution in executions) == (
        (1, 2, 14, 15, 26, 27),
        (3, 4, 16, 17, 28, 29),
    )
    for execution in executions:
        assert execution.emitted_main_numbers == execution.legal_main_numbers
        assert len(execution.legal_main_numbers) == 6
        assert len(set(execution.legal_main_numbers)) == 6
        assert all(1 <= number <= 49 for number in execution.legal_main_numbers)

    with pytest.raises(InsufficientHistory):
        adapter.get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(UnsupportedLotteryType):
        adapter.get_bets(history, LotteryType.POWER_LOTTO)


def test_catalog_registry_and_production_portfolio_path_are_reachable() -> None:
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
        BigLottoMinimalDualBetStrategyAdapter.strategy_id,
        BigLottoMinimalDualBetStrategyAdapter.strategy_name,
        BigLottoMinimalDualBetStrategyAdapter.strategy_version,
        (LotteryType.BIG_LOTTO,),
        LifecycleStatus.ONLINE,
        True,
        BigLottoMinimalDualBetStrategyAdapter.min_history,
        ResponseShape.PORTFOLIO,
        2,
    )
    assert ExecutableRegistry(catalog).load_adapter(STRATEGY_ID) is (
        BigLottoMinimalDualBetStrategyAdapter
    )
    assert "legacy_source:tools/minimal_dual_bet_strategy.py" in descriptor.provenance
    assert "current_significance:NOT_ESTABLISHED" in descriptor.provenance
    assert "predictive_advantage_claimed:NO" in descriptor.provenance

    request = GenerateOneBetInput(
        strategy_id=STRATEGY_ID,
        lottery_type=LotteryType.BIG_LOTTO,
        history=_weighted_history(),
    )
    result = build_production_generate_portfolio().execute(request)

    assert result.status is GeneratePortfolioStatus.OK
    assert result.numbers == (
        (1, 2, 14, 15, 26, 27),
        (3, 4, 16, 17, 28, 29),
    )


def test_production_catalog_appends_minimal_dual_bet_last_and_preserves_prior_order() -> None:
    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    assert len(all_ids) == 111
    # Scoped to the pre-PENDING_INTAKE_SET02_R1 prefix: minimal-dual-bet is
    # still last within it, and nothing in it moved.
    minimal_dual_bet_and_earlier = all_ids[:72]
    assert minimal_dual_bet_and_earlier[-1] == STRATEGY_ID
    assert minimal_dual_bet_and_earlier[:-1].count(STRATEGY_ID) == 0
    assert (
        minimal_dual_bet_and_earlier[-2]
        == "legacy_biglotto__backtest_biglotto_markov_4bet__aefb54eb345b"
    )
    assert (
        minimal_dual_bet_and_earlier[-3]
        == "legacy_composite__quick_predict_5bet_ts3_markov_freqort"
    )
