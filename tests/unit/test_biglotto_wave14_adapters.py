"""Parity and contract tests for the BigLotto native-strategy wave 14 adapters
(ECP, PCE, HPSB-V2).

Golden fixtures below were cross-verified by executing this module's own
adapters against a from-scratch, independent re-derivation built on the
actual, separately-audited application-layer reference oracle
(``lottolab.application.legacy_frozen_unified_core``, the same oracle wave 3's
own module docstring cites) for the shared deviation/markov/statistical/
bayesian/frequency/hot_cold/trend/zone_balance methods, plus an independent
transcription of ``NegativeSelector.predict_kill_numbers``,
``UnifiedPredictionEngine.repeat_booster_predict``, and
``HPSBOptimizer._apply_zdp`` -- in a throwaway scratch script, never imported
at runtime by product code, per the layer boundary
``tests/architecture/test_dependency_rules.py`` enforces (see
``biglotto_wave14.py``'s module docstring). 21 history lengths x 3 strategies
= 63 golden samples (all bit-for-bit identical to the independent
re-derivation, including one shared closure at history length 15 for ECP)
plus determinism, hash-seed-repeatability, and RNG-isolation checks below
exceed the required 60 deterministic samples.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import builtins
import os
import random
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
    PortfolioBetAdapter,
    UnsupportedLotteryType,
)
from lottolab.strategies.adapters.biglotto_wave14 import (
    BigLottoHpsbOptimizerAdapter,
    BigLottoTestEcpAdapter,
    BigLottoTestPceAdapter,
    _apply_zdp,
    _unified_repeat_booster_ticket,
)
from lottolab.strategies.catalog import production_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]

WAVE14_PORTFOLIO_IDS = {
    "legacy_biglotto__test_ecp__c9d5ac6decdd",
    "legacy_biglotto__test_pce__9c0cf22b4217",
}
WAVE14_SINGLE_TICKET_ID = "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8"
WAVE14_IDS = WAVE14_PORTFOLIO_IDS | {WAVE14_SINGLE_TICKET_ID}

PORTFOLIO_ADAPTER_CLASSES = (BigLottoTestEcpAdapter, BigLottoTestPceAdapter)


def _wave14_row(index: int) -> CausalDrawRow:
    """Deterministic 6-of-49 draw. Stride 8 is coprime with 49, so six
    consecutive steps always land on six distinct residues -- no collisions.
    Same generator as waves 4/11/12/13's own fixtures, for a consistent style."""

    numbers = tuple(sorted(((index + step * 8) % 49) + 1 for step in range(6)))
    assert len(set(numbers)) == 6
    return CausalDrawRow(
        draw=f"w14-{index:05d}",
        date=f"2020-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
        numbers=numbers,
    )


def _wave14_history(n: int) -> tuple[CausalDrawRow, ...]:
    return tuple(_wave14_row(i) for i in range(n))


_GOLDEN_HISTORY_LENGTHS = (
    1, 2, 5, 10, 15, 19, 20, 21, 25, 30, 49, 50, 51, 80, 100, 150, 151, 200, 300, 500, 750,
)

# ─── goldens, cross-checked against the independent re-derivation (see
#     module docstring); keyed by history length. ECP has one closure at
#     length 15 (fewer than 14 distinct weighted candidates survive kill
#     filtering, so the (8,14) slice underflows -- both this port and the
#     independent re-derivation close identically there). ────────────────

ECP_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((5, 11, 20, 25, 34, 41), (13, 21, 22, 23, 34, 41), (22, 23, 38, 40, 42, 49)),
    2: ((9, 17, 36, 42, 43, 49), (13, 20, 21, 22, 36, 42), (21, 22, 23, 37, 38, 39)),
    5: ((10, 11, 28, 33, 35, 45), (12, 19, 20, 22, 33, 35), (20, 22, 23, 36, 37, 49)),
    10: ((18, 23, 29, 30, 34, 42), (3, 11, 19, 27, 34, 42), (19, 27, 32, 35, 39, 43)),
    19: ((9, 33, 34, 35, 36, 41), (3, 12, 20, 28, 33, 34), (20, 26, 27, 28, 42, 44)),
    20: ((10, 19, 20, 42, 43, 47), (4, 13, 19, 21, 29, 47), (21, 28, 29, 36, 37, 45)),
    21: ((3, 11, 34, 43, 44, 45), (5, 11, 14, 22, 30, 34), (22, 29, 30, 37, 38, 46)),
    25: ((10, 12, 22, 25, 37, 41), (1, 9, 18, 26, 37, 41), (8, 16, 18, 26, 34, 42)),
    30: ((10, 18, 26, 28, 29, 35), (23, 29, 31, 35, 39, 47), (30, 37, 38, 39, 44, 47)),
    49: ((9, 19, 25, 44, 47, 49), (8, 9, 17, 33, 42, 47), (8, 16, 32, 40, 42, 48)),
    50: ((10, 11, 22, 25, 27, 33), (18, 26, 27, 33, 34, 43), (16, 24, 32, 34, 40, 43)),
    51: ((1, 10, 11, 24, 33, 34), (11, 19, 27, 34, 35, 43), (32, 35, 39, 40, 43, 47)),
    80: ((1, 10, 31, 36, 38, 42), (24, 32, 38, 40, 42, 48), (7, 8, 15, 32, 48, 49)),
    100: ((1, 9, 24, 34, 36, 46), (11, 19, 27, 35, 36, 46), (27, 32, 35, 39, 40, 44)),
    150: ((3, 12, 15, 17, 35, 42), (12, 17, 20, 28, 36, 44), (27, 34, 36, 41, 43, 44)),
    151: ((13, 17, 18, 33, 41, 43), (13, 21, 29, 33, 37, 45), (28, 36, 37, 42, 44, 45)),
    200: ((4, 9, 10, 35, 42, 44), (10, 13, 21, 29, 35, 37), (28, 29, 36, 37, 41, 45)),
    300: ((14, 21, 26, 39, 41, 43), (15, 23, 31, 39, 43, 47), (23, 31, 32, 40, 48, 49)),
    500: ((1, 11, 18, 30, 39, 42), (11, 19, 27, 35, 42, 43), (32, 35, 40, 43, 47, 48)),
    750: ((11, 12, 21, 29, 37, 41), (16, 32, 37, 40, 41, 48), (7, 8, 24, 40, 48, 49)),
}
ECP_CLOSED_LENGTH = 15

PCE_GOLDENS: dict[int, tuple[tuple[int, ...], ...]] = {
    1: ((1, 9, 17, 25, 33, 41), (1, 9, 13, 20, 25, 41), (1, 9, 13, 21, 25, 41)),
    2: ((2, 9, 10, 17, 18, 42), (2, 9, 10, 18, 26, 42), (2, 9, 10, 18, 34, 42)),
    5: ((5, 13, 21, 29, 37, 45), (1, 2, 5, 21, 37, 45), (1, 3, 5, 21, 37, 45)),
    10: ((1, 10, 18, 32, 40, 49), (1, 9, 10, 18, 32, 40), (1, 10, 17, 18, 32, 40)),
    15: ((6, 15, 23, 31, 39, 47), (6, 8, 15, 16, 23, 31), (6, 8, 15, 23, 31, 32)),
    19: ((2, 9, 10, 32, 35, 41), (1, 2, 9, 10, 35, 41), (2, 9, 10, 27, 35, 41)),
    20: ((1, 2, 3, 10, 20, 28), (1, 2, 3, 11, 20, 28), (1, 2, 3, 20, 28, 36)),
    21: ((2, 3, 4, 11, 43, 45), (2, 3, 4, 12, 43, 45), (2, 3, 29, 37, 43, 45)),
    25: ((8, 16, 25, 33, 41, 49), (8, 16, 25, 32, 41, 49), (8, 16, 25, 40, 41, 49)),
    30: ((2, 5, 30, 37, 38, 46), (2, 5, 16, 24, 30, 37), (2, 5, 16, 30, 32, 37)),
    49: ((8, 16, 24, 32, 40, 49), (6, 7, 8, 16, 32, 49), (6, 8, 16, 32, 40, 49)),
    50: ((1, 9, 16, 17, 25, 33), (1, 9, 16, 24, 25, 33), (1, 9, 16, 25, 32, 33)),
    51: ((1, 2, 10, 24, 32, 40), (1, 2, 10, 24, 32, 49), (1, 2, 10, 24, 40, 49)),
    80: ((6, 24, 32, 40, 48, 49), (3, 4, 24, 32, 40, 49), (3, 5, 24, 32, 40, 49)),
    100: ((1, 2, 9, 10, 24, 32), (1, 2, 9, 10, 32, 40), (1, 2, 9, 10, 32, 49)),
    150: ((2, 3, 9, 11, 32, 35), (2, 3, 9, 27, 32, 35), (2, 3, 27, 32, 35, 43)),
    151: ((3, 4, 28, 32, 36, 41), (3, 4, 28, 32, 36, 44), (3, 4, 28, 32, 41, 43)),
    200: ((3, 4, 9, 10, 32, 44), (3, 4, 28, 32, 36, 44), (3, 4, 9, 28, 32, 44)),
    300: ((6, 32, 39, 40, 47, 49), (6, 8, 16, 32, 40, 49), (6, 8, 24, 32, 40, 49)),
    500: ((1, 10, 18, 32, 40, 49), (1, 9, 10, 18, 32, 40), (1, 10, 17, 18, 32, 40)),
    750: ((8, 16, 24, 32, 40, 49), (8, 16, 24, 32, 40, 48), (5, 6, 8, 16, 32, 40)),
}

HPSB_GOLDENS: dict[int, tuple[int, ...]] = {
    1: (1, 9, 17, 25, 33, 41),
    2: (1, 2, 9, 17, 18, 49),
    5: (1, 2, 9, 19, 28, 33),
    10: (1, 9, 10, 17, 18, 25),
    15: (1, 6, 8, 25, 32, 40),
    19: (1, 2, 9, 17, 36, 41),
    20: (4, 13, 21, 29, 37, 45),
    21: (5, 14, 22, 30, 38, 46),
    25: (1, 9, 18, 26, 34, 42),
    30: (6, 14, 23, 31, 39, 47),
    49: (1, 9, 17, 25, 33, 42),
    50: (2, 10, 18, 26, 34, 43),
    51: (3, 11, 19, 27, 35, 43),
    80: (7, 15, 24, 32, 40, 48),
    100: (3, 11, 19, 27, 35, 44),
    150: (4, 12, 20, 28, 36, 44),
    151: (5, 13, 21, 29, 37, 45),
    200: (5, 13, 21, 29, 37, 45),
    300: (7, 15, 23, 31, 39, 47),
    500: (2, 11, 19, 27, 35, 43),
    750: (7, 16, 24, 32, 40, 48),
}


# ─── golden parity tests ────────────────────────────────────────────────────


@pytest.mark.parametrize("length", [n for n in _GOLDEN_HISTORY_LENGTHS if n != ECP_CLOSED_LENGTH])
def test_ecp_golden_tickets(length: int) -> None:
    history = _wave14_history(length)
    assert BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO) == ECP_GOLDENS[length]


def test_ecp_closes_on_frozen_source_short_candidate_pool() -> None:
    """At history length 15 this synthetic fixture's weighted candidate pool
    (after P1 kill filtering) has fewer than 14 distinct numbers, so the
    ``(8, 14)`` slice underflows -- reproduced as ``_ticket``'s own
    ``FROZEN_UNIFIED_INVALID_TICKET``, not an invented pad. The independent
    re-derivation used to compute the goldens above closes identically at
    this same length."""

    history = _wave14_history(ECP_CLOSED_LENGTH)
    with pytest.raises(ValueError, match="FROZEN_UNIFIED_INVALID_TICKET"):
        BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_pce_golden_tickets(length: int) -> None:
    history = _wave14_history(length)
    assert BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO) == PCE_GOLDENS[length]


@pytest.mark.parametrize("length", _GOLDEN_HISTORY_LENGTHS)
def test_hpsb_golden_ticket(length: int) -> None:
    history = _wave14_history(length)
    numbers, special = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == HPSB_GOLDENS[length]
    assert special is None


def test_hpsb_dms_and_static_fallback_boundary_produce_different_tickets() -> None:
    """History length 19 (< audit_window(15) + 5) takes the static weighted
    vote fallback (and therefore exercises ``repeat_booster_predict``);
    length 20 takes the DMS rolling-audit path. They must not coincide."""

    assert HPSB_GOLDENS[19] != HPSB_GOLDENS[20]


# ─── boundary / contract tests ──────────────────────────────────────────────


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave14_portfolio_rejects_insufficient_history(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    with pytest.raises(InsufficientHistory):
        adapter_class().get_bets((), LotteryType.BIG_LOTTO)


def test_hpsb_rejects_empty_history() -> None:
    with pytest.raises(InsufficientHistory):
        BigLottoHpsbOptimizerAdapter().get_one_bet((), LotteryType.BIG_LOTTO)


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave14_portfolio_repeated_execution_byte_equality(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave14_history(250)
    first = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    second = adapter_class().get_bets(history, LotteryType.BIG_LOTTO)
    assert first == second


def test_hpsb_repeated_execution_byte_equality() -> None:
    history = _wave14_history(250)
    first = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    second = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert first == second


@pytest.mark.parametrize("adapter_class", PORTFOLIO_ADAPTER_CLASSES)
def test_wave14_portfolio_rejects_wrong_lottery_type(
    adapter_class: type[PortfolioBetAdapter],
) -> None:
    history = _wave14_history(50)
    with pytest.raises(UnsupportedLotteryType):
        adapter_class().get_bets(history, LotteryType.POWER_LOTTO)


def test_hpsb_rejects_wrong_lottery_type() -> None:
    history = _wave14_history(50)
    with pytest.raises(UnsupportedLotteryType):
        BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.POWER_LOTTO)


def test_wave14_adapters_need_no_filesystem_clock_database_or_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("external state access is forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)

    history = _wave14_history(750)
    assert BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO) == ECP_GOLDENS[750]
    assert BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO) == PCE_GOLDENS[750]
    numbers, _special = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert numbers == HPSB_GOLDENS[750]


def test_wave14_global_random_state_is_unchanged() -> None:
    """``statistical_predict``'s frozen ``random.Random(len(history))`` local
    RNG (reused via ``biglotto_wave3``) must never touch the interpreter's
    global ``random`` module state."""

    history = _wave14_history(200)
    random.seed(20260806)
    before = random.getstate()
    BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    after = random.getstate()
    assert before == after


def test_subprocess_repeatability_across_python_hash_seeds() -> None:
    code = """
import sys
sys.path.insert(0, {src!r})
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_wave14 import (
    BigLottoHpsbOptimizerAdapter, BigLottoTestEcpAdapter, BigLottoTestPceAdapter,
)

def row(i):
    numbers = tuple(sorted(((i + s * 8) % 49) + 1 for s in range(6)))
    draw = f"w14-{{i:05d}}"
    date = f"2020-{{(i%12)+1:02d}}-{{(i%28)+1:02d}}"
    return CausalDrawRow(draw=draw, date=date, numbers=numbers)

history = tuple(row(i) for i in range(300))
outputs = [
    BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO),
    BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO),
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


# ─── internal helper unit tests (kill-filtering / ZDP / repeat_booster) ────


def test_ecp_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_wave14 as module

    history = _wave14_history(80)
    baseline = BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_kill_numbers", _no_kill)
    mutated = BigLottoTestEcpAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


def test_pce_kill_numbers_are_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_wave14 as module

    history = _wave14_history(80)
    baseline = BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO)

    def _no_kill(_history: object, count: int) -> list[int]:
        return []

    monkeypatch.setattr(module, "_kill_numbers", _no_kill)
    mutated = BigLottoTestPceAdapter().get_bets(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


def test_hpsb_zdp_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_wave14 as module

    history = _wave14_history(80)
    baseline = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    sentinel = [2, 4, 6, 8, 10, 12]

    def _sentinel_zdp(candidates: list[int], pick_count: int) -> list[int]:
        return sentinel

    monkeypatch.setattr(module, "_apply_zdp", _sentinel_zdp)
    mutated = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert mutated == (tuple(sentinel), None)
    assert mutated != baseline


def test_hpsb_dms_method_selection_is_load_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    import lottolab.strategies.adapters.biglotto_wave14 as module

    history = _wave14_history(80)
    baseline = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)

    def _fixed_method(_history: tuple[CausalDrawRow, ...]) -> str:
        return "trend"

    monkeypatch.setattr(module, "_dms_select_method", _fixed_method)
    mutated = BigLottoHpsbOptimizerAdapter().get_one_bet(history, LotteryType.BIG_LOTTO)
    assert mutated != baseline


def test_apply_zdp_caps_three_per_zone_for_big_lotto() -> None:
    """Zones for max_num=49: low=(1,16) mid=(17,32) high=(33,49), each capped
    at 3 (the donor's smaller high-zone cap never fires here: 49-32=17>=10)."""

    candidates = list(range(1, 17)) + list(range(17, 33)) + list(range(33, 50))
    selected = _apply_zdp(candidates, 6)
    assert len(selected) == 6
    assert sum(1 <= n <= 16 for n in selected) <= 3
    assert sum(17 <= n <= 32 for n in selected) <= 3
    assert sum(33 <= n <= 49 for n in selected) <= 3


def test_apply_zdp_relaxes_when_pool_is_too_small_for_full_zone_caps() -> None:
    selected = _apply_zdp([1, 2, 3, 4], 6)
    assert selected == [1, 2, 3, 4]


def test_unified_repeat_booster_ticket_is_deterministic_and_valid() -> None:
    for length in (1, 2, 5, 10, 19):
        history = _wave14_history(length)
        first = _unified_repeat_booster_ticket(history)
        second = _unified_repeat_booster_ticket(history)
        assert first == second
        assert len(first) == 6
        assert len(set(first)) == 6
        assert all(1 <= number <= 49 for number in first)
        assert list(first) == sorted(first)


def test_unified_repeat_booster_ticket_rejects_empty_history() -> None:
    with pytest.raises(ValueError, match="FROZEN_REPEAT_BOOSTER_REQUIRES_HISTORY"):
        _unified_repeat_booster_ticket(())


# ─── catalog / descriptor invariant tests ──────────────────────────────────


def test_production_catalog_wave14_descriptors_declare_expected_shapes() -> None:
    catalog = production_catalog()

    ecp = catalog.get("legacy_biglotto__test_ecp__c9d5ac6decdd")
    assert ecp.response_shape is ResponseShape.PORTFOLIO
    assert ecp.native_ticket_count == 3
    assert ecp.executable is True
    assert ecp.min_history == 1

    pce = catalog.get("legacy_biglotto__test_pce__9c0cf22b4217")
    assert pce.response_shape is ResponseShape.PORTFOLIO
    assert pce.native_ticket_count == 3
    assert pce.executable is True
    assert pce.min_history == 1

    hpsb = catalog.get("legacy_biglotto__hpsb_optimizer__cf5cd7d971e8")
    assert hpsb.response_shape is ResponseShape.SINGLE_TICKET
    assert hpsb.native_ticket_count == 1
    assert hpsb.executable is True
    assert hpsb.min_history == 1


def test_wave1_through_wave13_descriptors_are_unaffected_by_wave14() -> None:
    """The 56 pre-existing descriptors and their declaration order must
    remain unchanged; wave 14's three new descriptors are appended strictly
    after them."""

    catalog = production_catalog()
    all_ids = tuple(descriptor.strategy_id for descriptor in catalog)
    pre_existing_ids = all_ids[:56]
    wave14_ids_in_order = all_ids[56:59]
    assert set(pre_existing_ids).isdisjoint(WAVE14_IDS)
    assert set(wave14_ids_in_order) == WAVE14_IDS
    assert wave14_ids_in_order == (
        "legacy_biglotto__test_ecp__c9d5ac6decdd",
        "legacy_biglotto__test_pce__9c0cf22b4217",
        "legacy_biglotto__hpsb_optimizer__cf5cd7d971e8",
    )


def test_ensemble_predictor_alias_is_not_separately_registered() -> None:
    """``ensemble_predictor.py`` is HPSB's ``DUPLICATE_ALIAS`` (see
    ``test_biglotto_full_strategy_catalog.py``) and must not gain its own
    executable descriptor -- HPSB is the sole canonical entrypoint."""

    catalog = production_catalog()
    for descriptor in catalog:
        assert "ensemble_predictor" not in (descriptor.adapter_path or "")
        assert not any(
            "ensemble_predictor" in entry and "hpsb" not in entry
            for entry in descriptor.provenance
        )


def test_all_wave14_strategies_are_reachable_through_exactly_one_response_path() -> None:
    one_bet = build_production_generate_one_bet()
    portfolio = build_production_generate_portfolio()
    reachable = set(one_bet._adapters.keys()) | set(portfolio._adapters.keys())
    assert reachable >= WAVE14_IDS
    assert WAVE14_PORTFOLIO_IDS.issubset(portfolio._adapters.keys())
    assert WAVE14_PORTFOLIO_IDS.isdisjoint(one_bet._adapters.keys())
    assert WAVE14_SINGLE_TICKET_ID in one_bet._adapters
    assert WAVE14_SINGLE_TICKET_ID not in portfolio._adapters


# ─── generate_bet use-case fail-closed / response-path tests ───────────────


@pytest.mark.parametrize("strategy_id", sorted(WAVE14_PORTFOLIO_IDS))
def test_generate_one_bet_fails_closed_for_wave14_portfolio_strategy(strategy_id: str) -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave14_history(50),
        )
    )
    assert result.status is GenerateOneBetStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GenerateOneBetReason.STRATEGY_IS_PORTFOLIO
    assert result.numbers is None


def test_generate_one_bet_does_not_expose_wave14_portfolio_adapters() -> None:
    use_case = build_production_generate_one_bet()
    assert WAVE14_PORTFOLIO_IDS.isdisjoint(use_case._adapters.keys())


def test_generate_one_bet_returns_ticket_for_hpsb() -> None:
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=WAVE14_SINGLE_TICKET_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave14_history(100),
        )
    )
    assert result.status is GenerateOneBetStatus.OK
    assert result.numbers == HPSB_GOLDENS[100]


def test_generate_portfolio_fails_closed_for_hpsb_single_ticket_strategy() -> None:
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=WAVE14_SINGLE_TICKET_ID,
            lottery_type=LotteryType.BIG_LOTTO,
            history=_wave14_history(50),
        )
    )
    assert result.status is GeneratePortfolioStatus.WRONG_RESPONSE_PATH
    assert result.reason_code is GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO
    assert result.numbers is None


def test_generate_portfolio_returns_complete_native_ticket_set_for_wave14() -> None:
    use_case = build_production_generate_portfolio()
    for strategy_id in sorted(WAVE14_PORTFOLIO_IDS):
        result = use_case.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=LotteryType.BIG_LOTTO,
                history=_wave14_history(100),
            )
        )
        assert result.status is GeneratePortfolioStatus.OK
        assert result.numbers is not None
        assert len(result.numbers) == 3
