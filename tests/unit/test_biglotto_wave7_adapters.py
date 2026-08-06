"""Parity and production-path tests for BigLotto native strategy Wave 7."""

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
from lottolab.application.legacy_source_native_portfolios_wave8 import (
    GEMINI_PHASE2_METHOD_ID,
    LegacySourceNativeWave8Request,
    generate_legacy_source_native_wave8_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave15 import (
    ATTENTION_REPLAY_METHOD_ID,
    LegacySourceNativeWave15Request,
    generate_legacy_source_native_wave15_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave20 import (
    ZONE_BALANCE_500_METHOD_ID,
    LegacySourceNativeWave20Request,
    generate_legacy_source_native_wave20_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave22 import (
    SMART_2BET_METHOD_ID,
    LegacySourceNativeWave22Request,
    generate_legacy_source_native_wave22_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave23 import (
    FIVE_ME_METHOD_ID,
    LegacySourceNativeWave23Request,
    generate_legacy_source_native_wave23_portfolio,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetInput,
    GenerateOneBetReason,
    GenerateOneBetStatus,
    GeneratePortfolioReason,
    GeneratePortfolioStatus,
    build_production_generate_one_bet,
    build_production_generate_portfolio,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave7 import (
    BigLottoAttentionReplayAdapter,
    BigLottoFiveMeAdapter,
    BigLottoGeminiPhaseTwoVerifierAdapter,
    BigLottoSmartTwoBetAdapter,
    BigLottoZoneBalanceFiveAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE7_SINGLE_ADAPTER_CLASSES = (BigLottoAttentionReplayAdapter,)
WAVE7_PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoFiveMeAdapter,
    BigLottoSmartTwoBetAdapter,
    BigLottoGeminiPhaseTwoVerifierAdapter,
    BigLottoZoneBalanceFiveAdapter,
)
WAVE7_ADAPTER_CLASSES = (
    *WAVE7_PORTFOLIO_ADAPTER_CLASSES,
    *WAVE7_SINGLE_ADAPTER_CLASSES,
)
WAVE7_COUNTS = {
    BigLottoFiveMeAdapter.strategy_id: 5,
    BigLottoSmartTwoBetAdapter.strategy_id: 2,
    BigLottoGeminiPhaseTwoVerifierAdapter.strategy_id: 7,
    BigLottoZoneBalanceFiveAdapter.strategy_id: 5,
    BigLottoAttentionReplayAdapter.strategy_id: 1,
}
WAVE7_PORTFOLIO_COUNTS = {
    adapter_class.strategy_id: adapter_class.native_ticket_count
    for adapter_class in WAVE7_PORTFOLIO_ADAPTER_CLASSES
}


def _history(
    count: int,
    *,
    unpadded_offset: int = 0,
) -> tuple[CausalDrawRow, ...]:
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


def _single_reference(
    adapter_class: type[BigLottoAttentionReplayAdapter],
    history: tuple[CausalDrawRow, ...],
) -> tuple[int, ...]:
    assert adapter_class is BigLottoAttentionReplayAdapter
    return generate_legacy_source_native_wave15_portfolio(
        LegacySourceNativeWave15Request(
            legacy_method_id=ATTENTION_REPLAY_METHOD_ID,
            target_draw_number="target-after-causal-cutoff",
            history=_legacy_history(history),
        )
    ).tickets[0]


def _portfolio_reference(
    adapter_class: type[PortfolioBetAdapter],
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    legacy = _legacy_history(history)
    target = "target-after-causal-cutoff"
    if adapter_class is BigLottoFiveMeAdapter:
        return generate_legacy_source_native_wave23_portfolio(
            LegacySourceNativeWave23Request(
                legacy_method_id=FIVE_ME_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    if adapter_class is BigLottoSmartTwoBetAdapter:
        return generate_legacy_source_native_wave22_portfolio(
            LegacySourceNativeWave22Request(
                legacy_method_id=SMART_2BET_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    if adapter_class is BigLottoZoneBalanceFiveAdapter:
        return generate_legacy_source_native_wave20_portfolio(
            LegacySourceNativeWave20Request(
                legacy_method_id=ZONE_BALANCE_500_METHOD_ID,
                target_draw_number=target,
                history=legacy,
            )
        ).tickets
    return generate_legacy_source_native_wave8_portfolio(
        LegacySourceNativeWave8Request(
            legacy_method_id=GEMINI_PHASE2_METHOD_ID,
            target_draw_number=target,
            history=legacy,
        )
    ).tickets


@pytest.mark.parametrize("count", (1, 2, 49, 50, 100, 150, 250, 500))
@pytest.mark.parametrize(
    "adapter_class",
    (
        BigLottoFiveMeAdapter,
        BigLottoSmartTwoBetAdapter,
        BigLottoZoneBalanceFiveAdapter,
    ),
)
def test_wave7_portfolios_match_frozen_reference(
    count: int,
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history(count)
    assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == (
        _portfolio_reference(adapter_class, history)
    )


@pytest.mark.parametrize("count", (1, 2, 15, 16, 50, 150, 500))
def test_wave7_attention_replay_matches_frozen_reference(count: int) -> None:
    history = _history(count)
    ticket, special = BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert ticket == _single_reference(BigLottoAttentionReplayAdapter, history)
    assert special is None


@pytest.mark.parametrize("count", (100, 101, 150, 250, 500))
def test_wave7_gemini_phase_two_matches_frozen_reference(count: int) -> None:
    history = _history(count)
    assert BigLottoGeminiPhaseTwoVerifierAdapter().get_bets(
        history, LotteryType.BIG_LOTTO
    ) == _portfolio_reference(BigLottoGeminiPhaseTwoVerifierAdapter, history)


def test_wave7_all_methods_preserve_unpadded_draw_id_semantics() -> None:
    history = _history(146, unpadded_offset=97)
    assert history[0].draw > history[-1].draw
    for adapter_class in WAVE7_PORTFOLIO_ADAPTER_CLASSES:
        assert adapter_class().get_bets(
            history, LotteryType.BIG_LOTTO
        ) == _portfolio_reference(adapter_class, history)
    ticket, special = BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert ticket == _single_reference(BigLottoAttentionReplayAdapter, history)
    assert special is None


@pytest.mark.parametrize("adapter_class", WAVE7_PORTFOLIO_ADAPTER_CLASSES)
def test_wave7_fixed_count_order_duplicates_and_repeatability(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _history(250)
    expected = _portfolio_reference(adapter_class, history)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == expected
    assert second == first
    assert len(first) == adapter_class.native_ticket_count
    assert len(first) - len(set(first)) == len(expected) - len(set(expected))


def test_wave7_single_ticket_repeatability() -> None:
    history = _history(250)
    expected = _single_reference(BigLottoAttentionReplayAdapter, history)
    first = BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    second = BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    )
    assert first == (expected, None)
    assert second == first


def test_wave7_minimum_history_boundaries() -> None:
    for adapter_class in (
        BigLottoFiveMeAdapter,
        BigLottoSmartTwoBetAdapter,
        BigLottoZoneBalanceFiveAdapter,
    ):
        with pytest.raises(InsufficientHistory):
            adapter_class().get_bets((), LotteryType.BIG_LOTTO)
        assert len(
            adapter_class().get_bets(_history(1), LotteryType.BIG_LOTTO)
        ) == adapter_class.native_ticket_count
    with pytest.raises(InsufficientHistory):
        BigLottoGeminiPhaseTwoVerifierAdapter().get_bets(
            _history(99), LotteryType.BIG_LOTTO
        )
    assert len(
        BigLottoGeminiPhaseTwoVerifierAdapter().get_bets(
            _history(100), LotteryType.BIG_LOTTO
        )
    ) == 7
    with pytest.raises(InsufficientHistory):
        BigLottoAttentionReplayAdapter().get_one_bet(
            (), LotteryType.BIG_LOTTO
        )
    assert BigLottoAttentionReplayAdapter().get_one_bet(
        _history(1), LotteryType.BIG_LOTTO
    )[1] is None


@pytest.mark.parametrize("adapter_class", WAVE7_PORTFOLIO_ADAPTER_CLASSES)
def test_wave7_portfolios_reject_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(_history(250), LotteryType.POWER_LOTTO)


@pytest.mark.parametrize("adapter_class", WAVE7_SINGLE_ADAPTER_CLASSES)
def test_wave7_single_tickets_reject_wrong_lottery_type(
    adapter_class: type[BetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_one_bet(_history(250), LotteryType.POWER_LOTTO)


def test_wave7_adapters_need_no_filesystem_clock_database_or_network(
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
    for adapter_class in WAVE7_PORTFOLIO_ADAPTER_CLASSES:
        assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == (
            _portfolio_reference(adapter_class, history)
        )
    assert BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    ) == (
        _single_reference(BigLottoAttentionReplayAdapter, history),
        None,
    )


def test_wave7_repeatability_across_python_hash_seeds() -> None:
    code = """
import json, random, sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave7 import (
    BigLottoAttentionReplayAdapter, BigLottoFiveMeAdapter,
    BigLottoSmartTwoBetAdapter, BigLottoGeminiPhaseTwoVerifierAdapter,
    BigLottoZoneBalanceFiveAdapter,
)
rng = random.Random(20260802)
history = tuple(
    CausalDrawRow(
        draw=f"{{index + 1:09d}}", date="2020-01-01",
        numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
    )
    for index in range(250)
)
print(json.dumps({{
    "single": BigLottoAttentionReplayAdapter().get_one_bet(
        history, LotteryType.BIG_LOTTO
    ),
    "portfolios": [
        cls().get_bets(history, LotteryType.BIG_LOTTO)
        for cls in (
            BigLottoFiveMeAdapter, BigLottoSmartTwoBetAdapter,
            BigLottoGeminiPhaseTwoVerifierAdapter,
            BigLottoZoneBalanceFiveAdapter,
        )
    ],
}}))
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


def test_wave7_catalog_descriptors_and_response_paths() -> None:
    catalog = production_catalog()
    assert len(catalog) == 59
    for adapter_class in WAVE7_ADAPTER_CLASSES:
        descriptor = catalog.get(adapter_class.strategy_id)
        assert descriptor.strategy_name == adapter_class.strategy_name
        assert descriptor.min_history == adapter_class.min_history
        assert descriptor.executable is True
        assert descriptor.adapter_path is not None
        assert descriptor.adapter_path.endswith(f":{adapter_class.__name__}")
        assert (
            "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9"
            in descriptor.provenance
        )
        assert "migration_task:BIGLOTTO_NATIVE_STRATEGY_WAVE7_R1" in (
            descriptor.provenance
        )
    attention = catalog.get(BigLottoAttentionReplayAdapter.strategy_id)
    assert attention.response_shape is ResponseShape.SINGLE_TICKET
    assert attention.native_ticket_count == 1
    for adapter_class in WAVE7_PORTFOLIO_ADAPTER_CLASSES:
        descriptor = catalog.get(adapter_class.strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == adapter_class.native_ticket_count


@pytest.mark.parametrize("strategy_id", tuple(WAVE7_PORTFOLIO_COUNTS))
def test_generate_one_bet_fails_closed_for_wave7_portfolios(
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


def test_generate_one_bet_returns_wave7_attention_ticket() -> None:
    history = _history(250)
    result = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=BigLottoAttentionReplayAdapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.reason_code is None
    assert result.numbers == _single_reference(
        BigLottoAttentionReplayAdapter, history
    )


def test_generate_portfolio_returns_every_wave7_native_ticket() -> None:
    use_case = build_production_generate_portfolio()
    history = _history(250)
    for adapter_class in WAVE7_PORTFOLIO_ADAPTER_CLASSES:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=adapter_class.strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=history,
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers == _portfolio_reference(adapter_class, history)
        assert result.numbers is not None
        assert len(result.numbers) == adapter_class.native_ticket_count


def test_generate_portfolio_rejects_wave7_attention_single_ticket() -> None:
    result = build_production_generate_portfolio().execute(
        GenerateOneBetInput(
            strategy_id=BigLottoAttentionReplayAdapter.strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_history(250),
        )
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO
    assert result.numbers is None


def test_all_wave7_ids_are_reachable_only_on_their_declared_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    single_ids = {BigLottoAttentionReplayAdapter.strategy_id}
    portfolio_ids = set(WAVE7_PORTFOLIO_COUNTS)
    assert single_ids <= set(one_bet._adapters)
    assert single_ids.isdisjoint(portfolio._adapters)
    assert portfolio_ids.isdisjoint(one_bet._adapters)
    assert portfolio_ids <= set(portfolio._adapters)
    assert set(WAVE7_COUNTS) == single_ids | portfolio_ids
    assert set(one_bet._adapters).isdisjoint(portfolio._adapters)
