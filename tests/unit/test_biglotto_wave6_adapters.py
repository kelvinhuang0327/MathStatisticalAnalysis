"""Parity and production-path tests for BigLotto native strategy wave 6."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import random
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave23 import (
    TME_METHOD_ID,
    LegacySourceNativeWave23Request,
    generate_legacy_source_native_wave23_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave27 import (
    GEMINI_2BET_METHOD_ID,
    LegacySourceNativeWave27Request,
    generate_legacy_source_native_wave27_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave30 import (
    TEN_BET_METHOD_ID,
    LegacySourceNativeWave30Request,
    generate_legacy_source_native_wave30_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave34 import (
    AUTO_OPTIMIZER_METHOD_ID,
    LegacySourceNativeWave34Request,
    generate_legacy_source_native_wave34_portfolio,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
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
from lottolab.strategies.adapters.biglotto_wave6 import (
    BigLottoAutoOptimizerAlphaAdapter,
    BigLottoGeminiTwoBetVerifierAdapter,
    BigLottoTenBetBacktestAdapter,
    BigLottoTmeThreeAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE6_ADAPTER_CLASSES = (
    BigLottoAutoOptimizerAlphaAdapter,
    BigLottoTenBetBacktestAdapter,
    BigLottoTmeThreeAdapter,
    BigLottoGeminiTwoBetVerifierAdapter,
)
WAVE6_COUNTS = {
    BigLottoAutoOptimizerAlphaAdapter.strategy_id: 25,
    BigLottoTenBetBacktestAdapter.strategy_id: 10,
    BigLottoTmeThreeAdapter.strategy_id: 3,
    BigLottoGeminiTwoBetVerifierAdapter.strategy_id: 2,
}


def _history(count: int, *, unpadded_offset: int = 0) -> tuple[CausalDrawRow, ...]:
    rng = random.Random(20260802 + count + unpadded_offset)
    return tuple(
        CausalDrawRow(
            draw=(
                str(index + unpadded_offset)
                if unpadded_offset
                else f"{index + 1:09d}"
            ),
            date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(1, count + 1)
    )


def _legacy_history(
    history: tuple[CausalDrawRow, ...],
) -> tuple[LegacyHistoryDraw, ...]:
    return tuple(
        LegacyHistoryDraw(
            draw_number=row.draw,
            numbers=(
                row.numbers[0],
                row.numbers[1],
                row.numbers[2],
                row.numbers[3],
                row.numbers[4],
                row.numbers[5],
            ),
        )
        for row in history
    )


def _reference(
    adapter_class: type[PortfolioBetAdapter],
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    legacy = _legacy_history(history)
    target = "target-after-causal-cutoff"
    if adapter_class is BigLottoAutoOptimizerAlphaAdapter:
        return generate_legacy_source_native_wave34_portfolio(
            LegacySourceNativeWave34Request(
                legacy_method_id=AUTO_OPTIMIZER_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    if adapter_class is BigLottoTenBetBacktestAdapter:
        return generate_legacy_source_native_wave30_portfolio(
            LegacySourceNativeWave30Request(
                legacy_method_id=TEN_BET_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    if adapter_class is BigLottoTmeThreeAdapter:
        return generate_legacy_source_native_wave23_portfolio(
            LegacySourceNativeWave23Request(
                legacy_method_id=TME_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    return generate_legacy_source_native_wave27_portfolio(
        LegacySourceNativeWave27Request(
            legacy_method_id=GEMINI_2BET_METHOD_ID,
            target_draw_number=target,
            history=legacy,
        )
    ).tickets


@pytest.mark.parametrize("count", (1, 2, 49, 50, 100, 150, 250, 500))
@pytest.mark.parametrize(
    "adapter_class",
    WAVE6_ADAPTER_CLASSES[:-1],
)
def test_wave6_matches_frozen_reference(
    count: int,
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history(count)
    assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == (
        _reference(adapter_class, history)
    )


@pytest.mark.parametrize("count", (50, 51, 100, 150, 250, 500))
def test_wave6_gemini_two_bet_matches_frozen_reference(count: int) -> None:
    history = _history(count)
    assert BigLottoGeminiTwoBetVerifierAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    ) == _reference(BigLottoGeminiTwoBetVerifierAdapter, history)


@pytest.mark.parametrize("adapter_class", WAVE6_ADAPTER_CLASSES)
def test_wave6_randomized_unpadded_draw_id_parity(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    # "98" > "243" exercises the donor's text-ID Markov reversal guard.
    history = _history(146, unpadded_offset=97)
    assert history[0].draw > history[-1].draw
    assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == (
        _reference(adapter_class, history)
    )


@pytest.mark.parametrize("adapter_class", WAVE6_ADAPTER_CLASSES)
def test_wave6_fixed_count_order_duplicates_and_repeatability(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history(250)
    expected = _reference(adapter_class, history)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == expected
    assert second == first
    assert len(first) == adapter_class.native_ticket_count
    assert len(first) - len(set(first)) == len(expected) - len(set(expected))


def test_wave6_minimum_history_boundaries() -> None:
    for adapter_class in WAVE6_ADAPTER_CLASSES[:-1]:
        with pytest.raises(InsufficientHistory):
            adapter_class().get_bets((), LotteryType.BIG_LOTTO)
        assert len(adapter_class().get_bets(_history(1), LotteryType.BIG_LOTTO)) == (
            adapter_class.native_ticket_count
        )
    with pytest.raises(InsufficientHistory):
        BigLottoGeminiTwoBetVerifierAdapter().get_bets(
            _history(49), LotteryType.BIG_LOTTO
        )
    assert len(
        BigLottoGeminiTwoBetVerifierAdapter().get_bets(
            _history(50), LotteryType.BIG_LOTTO
        )
    ) == 2


@pytest.mark.parametrize("adapter_class", WAVE6_ADAPTER_CLASSES)
def test_wave6_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(_history(250), LotteryType.POWER_LOTTO)


def test_wave6_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    history = _history(250)
    for adapter_class in WAVE6_ADAPTER_CLASSES:
        assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == (
            _reference(adapter_class, history)
        )


def test_wave6_repeatability_across_python_hash_seeds() -> None:
    code = """
import json, random, sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave6 import (
    BigLottoAutoOptimizerAlphaAdapter, BigLottoTenBetBacktestAdapter,
    BigLottoTmeThreeAdapter, BigLottoGeminiTwoBetVerifierAdapter,
)
rng = random.Random(20260802)
history = tuple(
    CausalDrawRow(
        draw=f"{{index + 1:09d}}", date="2020-01-01",
        numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
    )
    for index in range(250)
)
print(json.dumps([
    cls().get_bets(history, LotteryType.BIG_LOTTO)
    for cls in (
        BigLottoAutoOptimizerAlphaAdapter, BigLottoTenBetBacktestAdapter,
        BigLottoTmeThreeAdapter, BigLottoGeminiTwoBetVerifierAdapter,
    )
]))
"""
    outputs: list[str] = []
    for hash_seed in ("1", "9173"):
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code.format(src=str(REPO_ROOT / "src"))],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]


def test_wave6_catalog_descriptors_and_response_paths() -> None:
    catalog = production_catalog()
    assert len(catalog) == 44
    for adapter_class in WAVE6_ADAPTER_CLASSES:
        descriptor = catalog.get(adapter_class.strategy_id)
        assert descriptor.strategy_name == adapter_class.strategy_name
        assert descriptor.min_history == adapter_class.min_history
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == adapter_class.native_ticket_count
        assert descriptor.executable is True
        assert descriptor.adapter_path is not None
        assert descriptor.adapter_path.endswith(f":{adapter_class.__name__}")
        assert (
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9"
            in descriptor.provenance
        )
        assert "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE6_R1" in (
            descriptor.provenance
        )


@pytest.mark.parametrize("strategy_id", tuple(WAVE6_COUNTS))
def test_generate_one_bet_fails_closed_for_wave6_portfolios(
    strategy_id: str,
) -> None:
    result = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(250),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_portfolio_returns_every_wave6_native_ticket() -> None:
    use_case = build_production_generate_portfolio()
    history = _history(250)
    for adapter_class in WAVE6_ADAPTER_CLASSES:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=adapter_class.strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers == _reference(adapter_class, history)
        assert result.numbers is not None
        assert len(result.numbers) == adapter_class.native_ticket_count


def test_all_wave6_ids_are_reachable_only_on_the_portfolio_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    assert set(WAVE6_COUNTS).isdisjoint(one_bet._adapters)
    assert set(WAVE6_COUNTS) <= set(portfolio._adapters)
    assert set(one_bet._adapters).isdisjoint(portfolio._adapters)
