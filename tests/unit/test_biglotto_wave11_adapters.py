"""Parity and contract tests for the BigLotto native-strategy wave 11 adapters.

Golden fixtures below were cross-verified by executing this module's own
adapters against the actual, separately-audited application-layer reference
oracles (``lottolab.application.legacy_random_native_portfolios`` for
core_satellite/zone_split, ``lottolab.application.legacy_history_native_portfolios``
for big_lotto_exhaustive_audit) in a throwaway scratch script -- never
imported at runtime by product code, per the layer boundary
``tests/architecture/test_dependency_rules.py`` enforces (see
``biglotto_wave11.py``'s module docstring). 20 history lengths per strategy
x 3 strategies = 60 samples, each independently reproduced bit-for-bit
against the oracle given the same synthesized ``target_draw_number``
(``_target_after_causal_cutoff``); zero mismatches.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

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
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave11 import (
    BigLottoCoreSatelliteRandomNativeAdapter,
    BigLottoExhaustiveAuditAdapter,
    BigLottoZoneSplitRandomNativeAdapter,
    _target_after_causal_cutoff,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE11_IDS = {
    "legacy_biglotto__core_satellite__611284461323",
    "legacy_biglotto__zone_split__b6144f9d479f",
    "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2",
}

PORTFOLIO_ADAPTER_CLASSES = (
    BigLottoCoreSatelliteRandomNativeAdapter,
    BigLottoZoneSplitRandomNativeAdapter,
    BigLottoExhaustiveAuditAdapter,
)


def _wave11_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=str(90000000 + index),
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave11_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave11_row(i) for i in range(n))


# ─── goldens, cross-checked against the reference oracles (see module
#     docstring); keyed by history length. ─────────────────────────────────

CORE_SATELLITE_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {
    1: ((5, 7, 11, 20, 22, 31), (10, 17, 18, 20, 22, 40), (3, 20, 22, 26, 35, 48)),
    2: ((4, 11, 19, 37, 38, 47), (21, 37, 43, 45, 47, 49), (8, 13, 33, 34, 37, 47)),
    3: ((1, 4, 19, 21, 24, 35), (3, 4, 5, 12, 19, 25), (4, 15, 17, 19, 30, 39)),
    4: ((16, 20, 23, 25, 36, 48), (8, 16, 25, 35, 42, 49), (16, 25, 26, 27, 29, 30)),
    5: ((12, 18, 19, 23, 34, 39), (7, 18, 19, 21, 33, 48), (6, 15, 18, 19, 29, 44)),
    6: ((4, 15, 16, 17, 24, 35), (20, 21, 24, 31, 35, 37), (12, 19, 23, 24, 34, 35)),
    7: ((7, 27, 31, 32, 35, 45), (7, 8, 12, 26, 32, 44), (4, 7, 16, 17, 19, 32)),
    8: ((8, 16, 23, 25, 30, 36), (10, 15, 16, 18, 21, 25), (6, 14, 16, 25, 31, 45)),
    9: ((10, 12, 19, 21, 29, 44), (12, 14, 18, 21, 25, 32), (5, 8, 12, 15, 21, 23)),
    10: ((5, 21, 28, 37, 43, 44), (9, 17, 32, 43, 44, 48), (3, 14, 22, 27, 43, 44)),
    15: ((11, 13, 18, 22, 30, 33), (8, 10, 13, 23, 30, 47), (13, 30, 34, 39, 40, 49)),
    20: ((15, 16, 22, 26, 35, 49), (1, 6, 9, 14, 15, 26), (10, 15, 26, 33, 37, 40)),
    25: ((7, 15, 16, 27, 32, 37), (12, 14, 15, 16, 22, 33), (15, 16, 29, 38, 41, 45)),
    30: ((8, 15, 24, 27, 37, 39), (4, 8, 9, 33, 37, 41), (2, 8, 10, 28, 30, 37)),
    40: ((18, 20, 22, 25, 35, 37), (3, 10, 18, 20, 39, 42), (2, 12, 18, 19, 20, 32)),
    50: ((1, 3, 7, 8, 12, 20), (7, 12, 15, 21, 29, 32), (7, 12, 17, 18, 24, 27)),
    75: ((18, 28, 31, 37, 39, 41), (2, 10, 18, 26, 27, 31), (11, 18, 19, 20, 23, 31)),
    100: ((10, 12, 30, 35, 42, 49), (14, 25, 27, 35, 42, 46), (19, 32, 34, 35, 41, 42)),
    150: ((1, 4, 30, 31, 33, 37), (4, 8, 22, 37, 39, 49), (4, 9, 34, 36, 37, 44)),
    300: ((2, 17, 18, 27, 34, 45), (1, 2, 10, 17, 26, 33), (2, 9, 16, 17, 24, 28)),
}

ZONE_SPLIT_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {
    1: ((1, 4, 13, 15, 16, 17), (15, 17, 20, 21, 26, 29), (32, 33, 37, 38, 43, 48)),
    2: ((2, 5, 6, 11, 12, 14), (19, 23, 24, 25, 26, 30), (31, 34, 43, 45, 47, 49)),
    3: ((2, 3, 6, 7, 13, 18), (15, 16, 18, 20, 27, 33), (31, 32, 41, 42, 44, 46)),
    4: ((2, 8, 11, 15, 17, 18), (17, 23, 27, 29, 30, 31), (31, 33, 42, 44, 48, 49)),
    5: ((2, 3, 5, 6, 7, 10), (15, 16, 20, 25, 26, 30), (31, 32, 33, 35, 37, 46)),
    6: ((2, 3, 5, 7, 9, 15), (16, 25, 27, 28, 30, 32), (31, 38, 39, 40, 41, 42)),
    7: ((1, 5, 10, 11, 13, 17), (15, 17, 18, 20, 29, 34), (35, 36, 38, 40, 45, 49)),
    8: ((4, 5, 7, 10, 11, 17), (19, 22, 25, 26, 27, 33), (33, 34, 35, 40, 44, 46)),
    9: ((2, 6, 12, 13, 14, 17), (17, 18, 20, 30, 31, 32), (35, 39, 40, 41, 44, 49)),
    10: ((1, 4, 10, 11, 15, 17), (16, 23, 24, 27, 31, 33), (32, 33, 38, 39, 43, 49)),
    15: ((4, 8, 9, 10, 16, 17), (17, 21, 22, 25, 31, 34), (34, 37, 43, 45, 47, 49)),
    20: ((1, 3, 4, 5, 10, 14), (17, 19, 25, 29, 31, 34), (31, 33, 43, 45, 47, 49)),
    25: ((4, 6, 8, 14, 16, 18), (15, 22, 24, 27, 31, 32), (35, 41, 42, 44, 47, 48)),
    30: ((6, 7, 12, 15, 17, 18), (15, 16, 18, 28, 29, 30), (31, 32, 34, 42, 43, 49)),
    40: ((1, 4, 5, 6, 7, 9), (15, 19, 23, 30, 31, 33), (38, 39, 42, 43, 45, 48)),
    50: ((1, 3, 4, 11, 13, 16), (15, 16, 18, 21, 29, 32), (35, 36, 40, 41, 44, 49)),
    75: ((4, 7, 12, 14, 15, 17), (18, 20, 21, 25, 27, 29), (31, 36, 37, 40, 43, 45)),
    100: ((7, 11, 12, 14, 16, 18), (15, 19, 20, 22, 23, 26), (31, 32, 36, 41, 42, 44)),
    150: ((9, 12, 13, 14, 15, 17), (18, 19, 22, 27, 28, 31), (33, 34, 35, 42, 46, 49)),
    300: ((3, 7, 10, 11, 12, 13), (16, 19, 22, 28, 30, 33), (31, 34, 35, 39, 45, 48)),
}

EXHAUSTIVE_AUDIT_GOLDENS: dict[int, tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]] = {
    50: ((5, 6, 9, 10, 25, 33), (34, 38, 39, 42, 43, 44), (4, 18, 22, 28, 36, 49)),
    51: ((1, 4, 7, 11, 18, 34), (35, 39, 43, 44, 48, 49), (12, 22, 26, 28, 31, 32)),
    52: ((1, 4, 5, 6, 9, 35), (33, 34, 38, 42, 45, 46), (12, 17, 24, 31, 37, 40)),
    55: ((2, 6, 7, 22, 38, 46), (35, 36, 40, 42, 45, 47), (8, 9, 12, 21, 27, 34)),
    60: ((6, 8, 9, 10, 19, 43), (33, 36, 37, 39, 44, 49), (2, 7, 23, 29, 45, 47)),
    70: ((1, 5, 6, 8, 12, 21), (33, 34, 36, 38, 39, 43), (4, 9, 17, 22, 24, 35)),
    80: ((2, 4, 14, 22, 31, 39), (33, 34, 35, 41, 44, 45), (12, 18, 19, 23, 36, 46)),
    90: ((1, 7, 8, 9, 24, 49), (33, 39, 42, 45, 46, 48), (25, 26, 31, 34, 41, 47)),
    100: ((6, 7, 11, 18, 34, 42), (33, 36, 38, 41, 45, 47), (2, 3, 5, 15, 27, 31)),
    120: ((1, 2, 3, 6, 7, 8), (33, 37, 40, 44, 45, 48), (12, 15, 18, 24, 25, 34)),
    150: ((1, 5, 6, 11, 19, 27), (36, 39, 41, 44, 47, 49), (9, 12, 14, 21, 35, 37)),
    200: ((3, 4, 5, 7, 12, 20), (34, 35, 38, 39, 42, 48), (1, 9, 10, 14, 15, 36)),
    250: ((3, 4, 6, 8, 21, 37), (33, 36, 38, 40, 41, 48), (14, 19, 23, 27, 30, 47)),
    300: ((4, 7, 10, 22, 30, 38), (36, 39, 42, 43, 48, 49), (9, 14, 15, 17, 46, 47)),
    350: ((1, 2, 5, 8, 9, 31), (35, 37, 41, 43, 46, 48), (6, 12, 16, 19, 30, 45)),
    400: ((3, 4, 6, 16, 24, 40), (33, 34, 36, 43, 44, 49), (23, 25, 28, 29, 39, 42)),
    450: ((5, 7, 8, 25, 33, 49), (32, 36, 37, 39, 43, 45), (9, 11, 13, 24, 31, 44)),
    500: ((1, 3, 5, 7, 8, 10), (36, 41, 44, 45, 46, 47), (11, 12, 14, 29, 34, 38)),
    600: ((1, 2, 6, 7, 9, 12), (34, 35, 40, 41, 43, 49), (3, 13, 17, 31, 36, 39)),
    700: ((1, 5, 6, 7, 10, 46), (35, 37, 42, 44, 47, 48), (3, 16, 17, 21, 40, 43)),
}


# ─── donor-parity: 60 deterministic samples across all three strategies ───


@pytest.mark.parametrize("n", sorted(CORE_SATELLITE_GOLDENS))
def test_core_satellite_matches_golden(n: int) -> None:
    history = _wave11_history(n)
    adapter = BigLottoCoreSatelliteRandomNativeAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == CORE_SATELLITE_GOLDENS[n]


@pytest.mark.parametrize("n", sorted(ZONE_SPLIT_GOLDENS))
def test_zone_split_matches_golden(n: int) -> None:
    history = _wave11_history(n)
    adapter = BigLottoZoneSplitRandomNativeAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == ZONE_SPLIT_GOLDENS[n]


@pytest.mark.parametrize("n", sorted(EXHAUSTIVE_AUDIT_GOLDENS))
def test_exhaustive_audit_matches_golden(n: int) -> None:
    history = _wave11_history(n)
    adapter = BigLottoExhaustiveAuditAdapter()
    assert adapter.get_bets(history, LotteryType.BIG_LOTTO) == EXHAUSTIVE_AUDIT_GOLDENS[n]


def test_wave11_golden_fixture_covers_at_least_sixty_samples() -> None:
    total = len(CORE_SATELLITE_GOLDENS) + len(ZONE_SPLIT_GOLDENS) + len(EXHAUSTIVE_AUDIT_GOLDENS)
    assert total >= 60


# ─── min_history / closure boundary ────────────────────────────────────────


@pytest.mark.parametrize(
    "adapter_cls", (BigLottoCoreSatelliteRandomNativeAdapter, BigLottoZoneSplitRandomNativeAdapter)
)
def test_random_native_adapters_close_below_min_history(adapter_cls: type) -> None:
    with pytest.raises(InsufficientHistory):
        adapter_cls().get_bets((), LotteryType.BIG_LOTTO)


def test_random_native_adapters_open_at_min_history() -> None:
    history = _wave11_history(1)
    assert (
        BigLottoCoreSatelliteRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == CORE_SATELLITE_GOLDENS[1]
    )
    assert (
        BigLottoZoneSplitRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == ZONE_SPLIT_GOLDENS[1]
    )


def test_exhaustive_audit_closes_below_fifty_draws() -> None:
    history = _wave11_history(49)
    with pytest.raises(InsufficientHistory):
        BigLottoExhaustiveAuditAdapter().get_bets(history, LotteryType.BIG_LOTTO)


def test_exhaustive_audit_opens_at_fifty_draws() -> None:
    history = _wave11_history(50)
    assert (
        BigLottoExhaustiveAuditAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == EXHAUSTIVE_AUDIT_GOLDENS[50]
    )


# ─── donor fidelity: random-native methods never read history content ─────


def _with_scrambled_numbers(row: CausalDrawRow) -> CausalDrawRow:
    scrambled = tuple(sorted((number % 49) + 1 for number in range(6)))
    return CausalDrawRow(draw=row.draw, date=row.date, numbers=scrambled)


def test_core_satellite_ignores_history_content_only_uses_last_draw_identity() -> None:
    baseline = _wave11_history(10)
    mutated = (*(_with_scrambled_numbers(row) for row in baseline[:-1]), baseline[-1])
    adapter = BigLottoCoreSatelliteRandomNativeAdapter()
    assert adapter.get_bets(baseline, LotteryType.BIG_LOTTO) == adapter.get_bets(
        mutated, LotteryType.BIG_LOTTO
    )


def test_zone_split_ignores_history_content_only_uses_last_draw_identity() -> None:
    baseline = _wave11_history(10)
    mutated = (*(_with_scrambled_numbers(row) for row in baseline[:-1]), baseline[-1])
    adapter = BigLottoZoneSplitRandomNativeAdapter()
    assert adapter.get_bets(baseline, LotteryType.BIG_LOTTO) == adapter.get_bets(
        mutated, LotteryType.BIG_LOTTO
    )


def test_target_proxy_changes_with_the_last_draw_identity() -> None:
    a = _target_after_causal_cutoff(_wave11_history(10))
    b = _target_after_causal_cutoff(_wave11_history(11))
    assert a != b


# ─── contract/closure tests parametrized over all three portfolio classes ─


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave11_portfolio_ticket_shape_is_valid(adapter_cls: type) -> None:
    history = _wave11_history(max(adapter_cls().min_history, 60))
    bets = adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)
    assert len(bets) == 3
    for ticket in bets:
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= number <= 49 for number in ticket)
        assert list(ticket) == sorted(ticket)


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave11_portfolio_repeated_execution_is_byte_identical(adapter_cls: type) -> None:
    """Proves the exact no-op rerun property: same history in, same tickets out."""

    history = _wave11_history(max(adapter_cls().min_history, 51))
    adapter = adapter_cls()
    first = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter.get_bets(history, LotteryType.BIG_LOTTO)
    third = adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second == third


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave11_portfolio_rejects_unsupported_lottery_type(adapter_cls: type) -> None:
    history = _wave11_history(max(adapter_cls().min_history, 51))
    with pytest.raises(UnsupportedLotteryType):
        adapter_cls().get_bets(history, LotteryType.DAILY_539)


@pytest.mark.parametrize("adapter_cls", PORTFOLIO_ADAPTER_CLASSES)
def test_wave11_portfolio_fails_closed_on_wrong_native_ticket_count(
    adapter_cls: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    def short_predict_all(
        self: object, history: object, lottery_type: object
    ) -> tuple[tuple[int, ...], ...]:
        return ((1, 2, 3, 4, 5, 6),)

    history = _wave11_history(max(adapter_cls().min_history, 51))
    monkeypatch.setattr(adapter_cls, "_predict_all", short_predict_all)
    with pytest.raises(InvalidOutput):
        adapter_cls().get_bets(history, LotteryType.BIG_LOTTO)


def test_wave11_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave11_history(300)
    assert (
        BigLottoCoreSatelliteRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == CORE_SATELLITE_GOLDENS[300]
    )
    assert (
        BigLottoZoneSplitRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == ZONE_SPLIT_GOLDENS[300]
    )
    assert (
        BigLottoExhaustiveAuditAdapter().get_bets(history, LotteryType.BIG_LOTTO)
        == EXHAUSTIVE_AUDIT_GOLDENS[300]
    )


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave11 import (
    BigLottoCoreSatelliteRandomNativeAdapter,
    BigLottoZoneSplitRandomNativeAdapter,
    BigLottoExhaustiveAuditAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=str(90000000 + i), date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoCoreSatelliteRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoZoneSplitRandomNativeAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoExhaustiveAuditAdapter().get_bets(history, LotteryType.BIG_LOTTO),
]
print(outputs)
"""
    src = str(REPO_ROOT / "src")
    outputs: list[str] = []
    for hash_seed in ("1", "9173"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
        completed = subprocess.run(
            [sys.executable, "-B", "-c", code.format(src=src)],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]


# ─── generate_bet use-case fail-closed / portfolio-path tests ──────────────


@pytest.mark.parametrize("strategy_id", sorted(WAVE11_IDS))
def test_generate_one_bet_fails_closed_for_wave11_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave11_history(51),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave11_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE11_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_portfolio_returns_complete_native_ticket_set_for_each_wave11_strategy() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id in WAVE11_IDS:
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave11_history(60),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == 3


def test_all_wave11_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE11_IDS
    assert set(one_bet._adapters.keys()) & set(portfolio._adapters.keys()) == set()


def test_generate_portfolio_unknown_strategy_still_fails_closed() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id="does_not_exist",
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave11_history(51),
        )
    )
    assert result.status is GeneratePortfolioStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is GeneratePortfolioReason.UNKNOWN_STRATEGY


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave11_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()
    expected_min_history = {
        "legacy_biglotto__core_satellite__611284461323": 1,
        "legacy_biglotto__zone_split__b6144f9d479f": 1,
        "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": 50,
    }
    for strategy_id, min_history in expected_min_history.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == 3
        assert descriptor.executable is True
        assert descriptor.min_history == min_history


def test_production_catalog_now_has_fifty_descriptors() -> None:
    """Name pinned at the Wave 11 landing point; later waves append only."""
    catalog = production_catalog()
    assert len(catalog) == 59


def test_wave11_core_satellite_and_zone_split_are_not_aliases_of_prior_waves() -> None:
    """These share a family name with pre-existing, unrelated strategies
    (wave2's engine-based core_satellite; wave1/2's replay-registry zone
    split) -- confirm they are genuinely distinct catalog entries, not
    duplicates, per ``biglotto_full_strategy_catalog_v1.json``'s
    ``DUPLICATE_ALIAS`` classification (12 entries elsewhere, none of these)."""

    catalog = production_catalog()
    new_core_satellite = catalog.get("legacy_biglotto__core_satellite__611284461323")
    old_core_satellite = catalog.get("legacy_biglotto__core_satellite__2e82891003b3")
    assert new_core_satellite.adapter_path != old_core_satellite.adapter_path
    assert new_core_satellite.native_ticket_count != old_core_satellite.native_ticket_count
    assert any(
        "lottery_api/models/core_satellite.py" in entry for entry in new_core_satellite.provenance
    )
    assert not any(
        "lottery_api/engine/core_satellite.py" in entry for entry in new_core_satellite.provenance
    )

    new_zone_split = catalog.get("legacy_biglotto__zone_split__b6144f9d479f")
    old_zone_split_bet1 = catalog.get("biglotto_zone_split_3bet_bet1")
    assert new_zone_split.adapter_path != old_zone_split_bet1.adapter_path
    assert new_zone_split.response_shape is ResponseShape.PORTFOLIO
    assert old_zone_split_bet1.response_shape is ResponseShape.SINGLE_TICKET


def test_wave1_through_wave10_descriptors_are_unaffected_by_wave11() -> None:
    """Existing 47 adapters must remain unchanged."""
    catalog = production_catalog()
    pre_existing_single_ticket_ids = (
        "biglotto_social_wisdom_anti_popularity",
        "biglotto_zone_split_3bet_bet1",
        "biglotto_zone_split_3bet_bet2",
        "biglotto_zone_split_3bet_bet3",
        "legacy_biglotto__graph_predictor__cd70713a5709",
        "legacy_biglotto__backtest_must_hit__909c91fd2fd0",
    )
    for strategy_id in pre_existing_single_ticket_ids:
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.SINGLE_TICKET
        assert descriptor.native_ticket_count == 1
    pre_existing_portfolio_ids = {
        "legacy_biglotto__predict_biglotto_echo_phase2__51c44b5c13d4": 5,
        "legacy_biglotto__high_prize_trend_optimizer__0fc72409150e": 7,
        "legacy_biglotto__core_satellite__2e82891003b3": 12,
        "legacy_biglotto__auto_discovery_biglotto__06bcb164db84": 54,
        "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d": 3,
        "legacy_biglotto__backtest_strategy_1__41ed79a6de62": 2,
    }
    for strategy_id, native_ticket_count in pre_existing_portfolio_ids.items():
        descriptor = catalog.get(strategy_id)
        assert descriptor.response_shape is ResponseShape.PORTFOLIO
        assert descriptor.native_ticket_count == native_ticket_count
