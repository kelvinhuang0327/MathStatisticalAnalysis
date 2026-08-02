"""Parity, portfolio, and production-registration tests for BigLotto wave 5.

The frozen donor scripts cannot be imported safely because their module shells
open legacy databases and, for UnifiedPredictionEngine callers, import the old
scientific/model stack.  Parity is therefore checked against the repository's
independently verified pure research ports, whose evidence records exact donor
byte/AST parity at commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``.
"""

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
from collections import Counter
from pathlib import Path

import pytest

from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
from lottolab.application.legacy_history_native_portfolios_wave5 import (
    ECHO_2BET_METHOD_ID,
    LegacyHistoryNativeWave5Request,
    generate_legacy_history_native_wave5_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave7 import (
    CLUSTER_6_METHOD_ID,
    CLUSTER_7_METHOD_ID,
    LegacySourceNativeWave7Request,
    generate_legacy_source_native_wave7_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave28 import (
    ELITE_SEVEN_METHOD_ID,
    LegacySourceNativeWave28Request,
    generate_legacy_source_native_wave28_portfolio,
)
from lottolab.application.legacy_source_native_portfolios_wave32 import (
    VARIANT_HISTORY_METHOD_ID,
    LegacySourceNativeWave32Request,
    generate_legacy_source_native_wave32_portfolio,
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
    InvalidOutput,
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave5 import (
    BigLottoEchoTwoBetAdapter,
    BigLottoEliteSevenAdapter,
    BigLottoSevenBetClusterAdapter,
    BigLottoSixBetClusterAdapter,
    BigLottoVariantHistoryAdapter,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE5_COUNTS = {
    BigLottoSixBetClusterAdapter.strategy_id: 6,
    BigLottoSevenBetClusterAdapter.strategy_id: 7,
    BigLottoEchoTwoBetAdapter.strategy_id: 2,
    BigLottoEliteSevenAdapter.strategy_id: 7,
    BigLottoVariantHistoryAdapter.strategy_id: 11,
}
WAVE5_ADAPTER_CLASSES = (
    BigLottoSixBetClusterAdapter,
    BigLottoSevenBetClusterAdapter,
    BigLottoEchoTwoBetAdapter,
    BigLottoEliteSevenAdapter,
    BigLottoVariantHistoryAdapter,
)
REFERENCE_LENGTHS = (1, 2, 3, 5, 10, 20, 30, 49, 50, 51, 80, 100, 150, 200, 250, 500)


def _wave5_row(index: int) -> CausalDrawRow:
    numbers = tuple(sorted(((index * 7 + offset * 5) % 49) + 1 for offset in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"{index + 1:09d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave5_history(count: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave5_row(index) for index in range(count))


def _legacy_history(history: tuple[CausalDrawRow, ...]) -> tuple[LegacyHistoryDraw, ...]:
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


@pytest.mark.parametrize("count", REFERENCE_LENGTHS)
@pytest.mark.parametrize(
    ("adapter_class", "method_id"),
    (
        (BigLottoSixBetClusterAdapter, CLUSTER_6_METHOD_ID),
        (BigLottoSevenBetClusterAdapter, CLUSTER_7_METHOD_ID),
    ),
)
def test_cluster_portfolios_match_frozen_reference_or_same_early_closure(
    count: int,
    adapter_class: type[PortfolioBetAdapter],
    method_id: str,
) -> None:
    history = _wave5_history(count)
    try:
        expected = generate_legacy_source_native_wave7_portfolio(
            LegacySourceNativeWave7Request(
                legacy_method_id=method_id,
                target_draw_number=f"{count + 1:09d}",
                history=_legacy_history(history),
            )
        ).tickets
    except ValueError:
        with pytest.raises(InvalidOutput):
            adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    else:
        assert adapter_class().get_bets(history, LotteryType.BIG_LOTTO) == expected


@pytest.mark.parametrize("count", REFERENCE_LENGTHS)
def test_echo_two_bet_matches_frozen_reference(count: int) -> None:
    history = _wave5_history(count)
    expected = generate_legacy_history_native_wave5_portfolio(
        LegacyHistoryNativeWave5Request(
            legacy_method_id=ECHO_2BET_METHOD_ID,
            target_draw_number=f"{count + 1:09d}",
            history=_legacy_history(history),
        )
    ).tickets
    assert BigLottoEchoTwoBetAdapter().get_bets(history, LotteryType.BIG_LOTTO) == expected


@pytest.mark.parametrize("count", REFERENCE_LENGTHS)
def test_elite_seven_matches_frozen_reference(count: int) -> None:
    history = _wave5_history(count)
    expected = generate_legacy_source_native_wave28_portfolio(
        LegacySourceNativeWave28Request(
            legacy_method_id=ELITE_SEVEN_METHOD_ID,
            target_draw_number=f"{count + 1:09d}",
            history=_legacy_history(history),
        )
    ).tickets
    assert BigLottoEliteSevenAdapter().get_bets(history, LotteryType.BIG_LOTTO) == expected


@pytest.mark.parametrize("count", tuple(n for n in REFERENCE_LENGTHS if n >= 20))
def test_variant_history_matches_frozen_reference(count: int) -> None:
    history = _wave5_history(count)
    expected = generate_legacy_source_native_wave32_portfolio(
        LegacySourceNativeWave32Request(
            legacy_method_id=VARIANT_HISTORY_METHOD_ID,
            target_draw_number=f"{count + 1:09d}",
            history=_legacy_history(history),
        )
    ).tickets
    assert BigLottoVariantHistoryAdapter().get_bets(history, LotteryType.BIG_LOTTO) == expected


def test_variant_history_matches_frozen_reference_for_unpadded_draw_ids() -> None:
    rng = random.Random(20260802)
    history = tuple(
        CausalDrawRow(
            draw=str(index + 1),
            date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
            numbers=tuple(sorted(rng.sample(range(1, 50), 6))),
        )
        for index in range(146)
    )
    expected = generate_legacy_source_native_wave32_portfolio(
        LegacySourceNativeWave32Request(
            legacy_method_id=VARIANT_HISTORY_METHOD_ID,
            target_draw_number="147",
            history=_legacy_history(history),
        )
    ).tickets
    actual = BigLottoVariantHistoryAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert actual == expected


WAVE5_GOLDENS_250 = {
    BigLottoSixBetClusterAdapter.strategy_id: (
        (5, 29, 34, 39, 44, 49),
        (22, 29, 34, 39, 44, 49),
        (27, 32, 34, 39, 44, 49),
        (34, 37, 39, 42, 44, 49),
        (15, 39, 42, 44, 47, 49),
        (20, 25, 42, 44, 47, 49),
    ),
    BigLottoSevenBetClusterAdapter.strategy_id: (
        (5, 29, 34, 39, 44, 49),
        (22, 29, 34, 39, 44, 49),
        (27, 32, 34, 39, 44, 49),
        (34, 37, 39, 42, 44, 49),
        (15, 39, 42, 44, 47, 49),
        (20, 25, 42, 44, 47, 49),
        (22, 30, 42, 44, 47, 49),
    ),
    BigLottoEchoTwoBetAdapter.strategy_id: (
        (5, 29, 34, 39, 44, 49),
        (3, 10, 17, 24, 31, 38),
    ),
    BigLottoEliteSevenAdapter.strategy_id: (
        (8, 13, 18, 23, 28, 33),
        (15, 20, 25, 30, 35, 40),
        (10, 11, 16, 17, 38, 45),
        (10, 11, 12, 14, 16, 17),
        (11, 18, 23, 35, 40, 49),
        (1, 26, 32, 35, 37, 47),
        (10, 11, 18, 23, 35, 40),
    ),
    BigLottoVariantHistoryAdapter.strategy_id: (
        (3, 10, 17, 24, 31, 38),
        (10, 13, 15, 16, 17, 18),
        (10, 11, 12, 14, 16, 17),
        (2, 5, 6, 32, 39, 49),
        (7, 22, 27, 32, 34, 46),
        (2, 23, 25, 28, 32, 33),
        (2, 7, 12, 36, 41, 46),
        (2, 7, 12, 36, 41, 46),
        (2, 7, 12, 36, 41, 46),
        (3, 10, 17, 24, 31, 38),
        (5, 22, 27, 29, 32, 34),
    ),
}


@pytest.mark.parametrize("adapter_class", WAVE5_ADAPTER_CLASSES)
def test_wave5_fixed_golden_count_order_and_repeatability(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave5_history(250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == WAVE5_GOLDENS_250[adapter_class.strategy_id]
    assert second == first
    assert len(first) == adapter_class.native_ticket_count


def test_wave5_load_bearing_portfolio_semantics_are_preserved() -> None:
    history = _wave5_history(250)
    six = BigLottoSixBetClusterAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    seven = BigLottoSevenBetClusterAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    echo = BigLottoEchoTwoBetAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    elite = BigLottoEliteSevenAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    variants = BigLottoVariantHistoryAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    assert seven[:6] == six
    assert set(echo[0]).isdisjoint(echo[1])
    consensus = Counter(number for ticket in elite[:6] for number in ticket).most_common(6)
    assert elite[6] == tuple(sorted(number for number, _count in consensus))
    assert variants[6] == variants[7] == variants[8]
    assert variants[0] == variants[9]


@pytest.mark.parametrize("adapter_class", WAVE5_ADAPTER_CLASSES)
def test_wave5_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(_wave5_history(250), LotteryType.POWER_LOTTO)


def test_wave5_minimum_history_boundaries() -> None:
    for adapter_class in WAVE5_ADAPTER_CLASSES[:-1]:
        with pytest.raises(InsufficientHistory):
            adapter_class().get_bets((), LotteryType.BIG_LOTTO)
    with pytest.raises(InsufficientHistory):
        BigLottoVariantHistoryAdapter().get_bets(_wave5_history(19), LotteryType.BIG_LOTTO)
    assert (
        len(BigLottoVariantHistoryAdapter().get_bets(_wave5_history(20), LotteryType.BIG_LOTTO))
        == 11
    )


def test_wave5_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    history = _wave5_history(250)
    for adapter_class in WAVE5_ADAPTER_CLASSES:
        assert (
            adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
            == WAVE5_GOLDENS_250[adapter_class.strategy_id]
        )


def test_wave5_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave5 import (
    BigLottoSixBetClusterAdapter, BigLottoSevenBetClusterAdapter,
    BigLottoEchoTwoBetAdapter, BigLottoEliteSevenAdapter,
    BigLottoVariantHistoryAdapter,
)
history = tuple(
    CausalDrawRow(
        draw=f"{{i + 1:09d}}", date=f"2020-{{(i % 12) + 1:02d}}-01",
        numbers=tuple(sorted(((i * 7 + offset * 5) % 49) + 1 for offset in range(6))),
    )
    for i in range(250)
)
print([
    cls().get_bets(history, LotteryType.BIG_LOTTO)
    for cls in (
        BigLottoSixBetClusterAdapter, BigLottoSevenBetClusterAdapter,
        BigLottoEchoTwoBetAdapter, BigLottoEliteSevenAdapter,
        BigLottoVariantHistoryAdapter,
    )
])
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


def test_wave5_catalog_descriptors_and_response_paths() -> None:
    catalog = production_catalog()
    assert len(catalog) == 28
    for strategy_id, native_ticket_count in WAVE5_COUNTS.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
        assert descriptor.executable is True
        assert "legacy_commit:49a25effa62fc24f40789c16be6f11bdfb41a4a9" in (descriptor.provenance)


@pytest.mark.parametrize("strategy_id", tuple(WAVE5_COUNTS))
def test_generate_one_bet_fails_closed_for_wave5_portfolios(strategy_id: str) -> None:
    result = build_production_generate_one_bet().execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave5_history(250),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_portfolio_returns_every_wave5_native_ticket() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id, expected_count in WAVE5_COUNTS.items():
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave5_history(250),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert result.numbers == WAVE5_GOLDENS_250[strategy_id]
        assert len(result.numbers) == expected_count


def test_all_wave5_ids_are_reachable_only_on_the_portfolio_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    assert set(WAVE5_COUNTS).isdisjoint(one_bet._adapters)
    assert set(WAVE5_COUNTS) <= set(portfolio._adapters)
    assert set(one_bet._adapters).isdisjoint(portfolio._adapters)
